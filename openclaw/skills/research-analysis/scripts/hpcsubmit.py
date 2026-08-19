#!/usr/bin/env python3
"""
hpcsubmit.py — HPC 分析提交器
"""

import sys, os, json, argparse
from pathlib import Path
import pexpect


def load_credentials() -> tuple:
    user = os.environ.get("HPC_USER") or ""
    passwd = os.environ.get("HPC_PASS") or ""
    if user and passwd:
        return user, passwd
    lp = os.path.expanduser("~/login_info_vpn.txt")
    if os.path.exists(lp):
        with open(lp) as f:
            data = {}
            for line in f:
                line = line.strip()
                if ":" in line:
                    k, v = line.split(":", 1)
                    data[k.strip()] = v.strip()
            return data.get("username", "stu2188"), data.get("passwd", "ym56aPnEeT")
    return "stu2188", "ym56aPnEeT"


def sp(cmd: str, timeout: int = 300):
    return pexpect.spawn(cmd, timeout=timeout, encoding="utf-8",
                         codec_errors="replace", maxread=4000)


def sendpw(child, passwd, tries=2):
    for _ in range(tries):
        idx = child.expect_exact(["Enter your HPC", "password:", "Password:",
                                   pexpect.TIMEOUT], timeout=15)
        if idx == 3:
            return False
        child.sendline(passwd)
    return True


def login_kp(user, passwd, timeout=30):
    """双跳登录 kplogin1，设置唯一 PS1 后返回 child。"""
    # 第一跳：pilogin（2次密码）
    child = sp(f"ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 "
               f"{user}@pilogin.hpc.sjtu.edu.cn")
    if not sendpw(child, passwd, tries=2):
        print("  pilogin 认证失败", file=sys.stderr)
        child.close()
        return None
    try:
        child.expect_exact("pilogin", timeout=timeout)
        child.sendline("echo _PI_OK_")
        child.expect_exact("_PI_OK_", timeout=timeout)
    except Exception:
        child.close()
        return None

    # 第二跳：kplogin1（1次密码）
    child.sendline("ssh -o StrictHostKeyChecking=accept-new kplogin1")
    if not sendpw(child, passwd, tries=1):
        child.close()
        return None
    try:
        child.expect_exact("kplogin1", timeout=timeout)
        child.sendline("echo _KP_OK_")
        child.expect_exact("_KP_OK_", timeout=timeout)
    except Exception:
        child.close()
        return None

    # 设置唯一 PS1
    child.sendline("export PS1='KPL_RUN> '")
    child.expect_exact("KPL_RUN>", timeout=10)
    return child


def close(child):
    try:
        child.sendline("exit")
        child.expect(pexpect.EOF, timeout=5)
    except Exception:
        pass
    try:
        child.close()
    except Exception:
        pass


def run(child, cmd, timeout=600):
    """在 child 中执行命令，返回 stdout。"""
    child.sendline(cmd)
    child.expect_exact("KPL_RUN>", timeout=timeout)
    raw = child.before.strip()
    lines = raw.split("\n")
    if lines and lines[0].strip() == cmd:
        lines = lines[1:]
    return "\n".join(lines).strip()


# ===================================================================
# SCP
# ===================================================================

def _scp(src, dst, passwd, timeout=180):
    child = sp(f"scp -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 "
               f"{src} {dst}", timeout)
    for _ in range(3):
        idx = child.expect_exact(["Enter your HPC", "password:", "Password:",
                                   pexpect.EOF, pexpect.TIMEOUT], timeout=30)
        if idx == 3:
            child.close()
            return True
        if idx == 4:
            child.close()
            return False
        child.sendline(passwd)
    try:
        child.expect(pexpect.EOF, timeout=timeout)
    except Exception:
        pass
    child.close()
    return True


def upload(local, user, passwd, timeout=180):
    fn = os.path.basename(local)
    print(f"  📤 {fn}")
    if not _scp(local, f"{user}@pilogin.hpc.sjtu.edu.cn:~/hpc_analysis/",
                passwd, timeout):
        return False
    child = login_kp(user, passwd, timeout=timeout)
    if child is None:
        return False
    child.sendline(f"scp -o StrictHostKeyChecking=accept-new "
                   f"~/hpc_analysis/{fn} {user}@kplogin1:~/hpc_analysis/")
    for _ in range(3):
        idx = child.expect_exact(["KPL_RUN>", "Enter your HPC", "password:",
                                   "Password:", pexpect.TIMEOUT], timeout=timeout)
        if idx == 0:
            break
        if idx in (1, 2, 3):
            child.sendline(passwd)
            continue
        if idx == 4:
            close(child)
            return False
    close(child)
    return True


def download(local_dir, pat, user, passwd, timeout=180):
    print(f"  📥 {pat}")
    # kplogin1 → pilogin
    child = login_kp(user, passwd, timeout=timeout)
    if child is None:
        return False
    child.sendline(f"scp -o StrictHostKeyChecking=accept-new "
                   f"{user}@kplogin1:~/hpc_analysis/{pat} ~/hpc_analysis/")
    for _ in range(3):
        idx = child.expect_exact(["KPL_RUN>", "Enter your HPC", "password:",
                                   "Password:", pexpect.TIMEOUT], timeout=timeout)
        if idx == 0:
            break
        if idx in (1, 2, 3):
            child.sendline(passwd)
            continue
        if idx == 4:
            close(child)
            return False
    close(child)
    # pilogin → local
    return _scp(f"{user}@pilogin.hpc.sjtu.edu.cn:~/hpc_analysis/{pat}",
                f"{local_dir}/", passwd, timeout)


# ===================================================================
# 主流程
# ===================================================================

def run_on_hpc(decision, user, passwd):
    pipe = decision["pipeline"]
    data_csv = pipe["data_csv"]
    method = pipe["method"]
    y_col = pipe["y_col"]
    x_vars = pipe["x_vars"]
    op = pipe["output_prefix"]
    dfn = os.path.basename(data_csv)
    sd = Path(__file__).parent.resolve()
    skd = sd.parent

    print("\n🔗 连接 kplogin1...")
    child = login_kp(user, passwd, timeout=30)
    if child is None:
        return None
    print("  ✅ 登录成功")
    run(child, "mkdir -p ~/hpc_analysis", timeout=10)

    print("\n🔍 环境检查...")
    for pkg in ["python3 --version", "pandas", "numpy", "scipy", "sklearn"]:
        c = pkg if pkg.startswith("python3") else f'python3 -c "import {pkg}; print({pkg}.__version__)"'
        try:
            out = run(child, c, timeout=15)
            print(f"  {pkg}: {out.strip().split(chr(10))[-1]}")
        except Exception:
            print(f"  {pkg}: ?")
    close(child)

    print("\n📤 上传...")
    ch2 = login_kp(user, passwd, timeout=30)
    if ch2:
        run(ch2, "mkdir -p ~/hpc_analysis", timeout=5)
        close(ch2)
    for f in [data_csv] + [str(sd / s) for s in
                           ["statisticsexecutor.py", "figuregenerator.py"]
                           if (sd / s).exists()]:
        if not upload(f, user, passwd):
            return None

    print("\n⚡ 执行...")
    ch3 = login_kp(user, passwd, timeout=30)
    if ch3 is None:
        return None
    xa = " ".join(f"'{x}'" for x in x_vars) if x_vars else ""
    cmd = (f"cd ~/hpc_analysis && python3 statisticsexecutor.py "
           f"'{dfn}' -m {method} -y '{y_col}' "
           f"{'-x ' + xa if xa else ''} -o '{op}' 2>&1")
    print(f"\n📊 {method}...")
    try:
        print(run(ch3, cmd, timeout=600))
    except Exception as e:
        print(f"  ⚠️ 超时: {e}")

    try:
        cmd2 = (f"cd ~/hpc_analysis && python3 figuregenerator.py "
                f"'{dfn}' '{op}.json' -t all -o '{op}_figure' 2>&1")
        print(f"\n🎨 图表...")
        print(run(ch3, cmd2, timeout=600))
    except Exception as e:
        print(f"  ⚠️ 超时: {e}")

    ls = run(ch3,
             f"ls -la ~/hpc_analysis/{op}* 2>/dev/null; "
             f"ls -la ~/hpc_analysis/figures/ 2>/dev/null || true",
             timeout=15)
    print(f"\n📋 输出:\n{ls}")
    close(ch3)

    print("\n📥 下载...")
    lr, lf = skd / "results", skd / "figures"
    os.makedirs(lr, exist_ok=True), os.makedirs(lf, exist_ok=True)
    download(str(lr), f"{op}*", user, passwd)
    download(str(lf), f"figures/{op}_figure*", user, passwd)
    return {"result_json": str(lr / f"{op}.json"),
            "summary_md": str(lr / f"{op}_summary.md"),
            "figures_dir": str(lf)}


def main():
    p = argparse.ArgumentParser(description="🖥️ HPCSubmit")
    p.add_argument("data_csv")
    p.add_argument("decision_json")
    args = p.parse_args()
    with open(args.decision_json, encoding="utf-8") as f:
        decision = json.load(f)
    user, passwd = load_credentials()
    print(f"🔑 {user}")
    r = run_on_hpc(decision, user, passwd)
    if r:
        print(f"\n✅ HPC 分析完成!")
        print(f"   📊 结果: {r['result_json']}")
        if os.path.exists(r['result_json']):
            print(f"💡 reportgenerator.py {r['result_json']} --data {args.data_csv} -o final_report")
    else:
        print("\n❌ 失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
