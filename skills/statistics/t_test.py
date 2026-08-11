import pandas as pd
import numpy as np
from scipy import stats


def _to_python(value):
    """
    将 numpy 类型转换成 Python 原生类型，
    方便后续 JSON 序列化。
    """
    if pd.isna(value):
        return None

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.floating):
        return float(value)

    if isinstance(value, np.bool_):
        return bool(value)

    return value


def _calculate_cohens_d(group1, group2, equal_var):
    """
    计算 Cohen's d。

    equal_var=True：
        使用 pooled standard deviation。

    equal_var=False：
        使用 Welch 风格的标准化差异，
        使用两个样本标准差的平方平均作为标准化尺度。
    """

    n1 = len(group1)
    n2 = len(group2)

    mean1 = group1.mean()
    mean2 = group2.mean()

    std1 = group1.std(ddof=1)
    std2 = group2.std(ddof=1)

    if equal_var:
        # Pooled standard deviation
        pooled_std = np.sqrt(
            (
                (n1 - 1) * std1 ** 2
                + (n2 - 1) * std2 ** 2
            )
            / (n1 + n2 - 2)
        )

        if pooled_std == 0:
            return None

        return (mean1 - mean2) / pooled_std

    else:
        # Welch / unequal variance effect size
        standardizer = np.sqrt(
            (std1 ** 2 + std2 ** 2) / 2
        )

        if standardizer == 0:
            return None

        return (mean1 - mean2) / standardizer


def run(request: dict) -> dict:
    """
    比较两个独立组的数值型目标变量均值是否存在显著差异。

    输入格式：

    {
        "data_path": "outputs/uploads/task_xxx/cleaned.csv",
        "params": {
            "target_column": "yield",
            "group_column": "fertilizer",
            "groups": ["A", "B"],
            "equal_var": "auto",
            "alternative": "two-sided",
            "alpha": 0.05
        }
    }

    输出格式：

    {
        "summary": {
            "test": "welch_t_test",
            "group_1": "A",
            "group_2": "B",
            "mean_1": 21.4,
            "mean_2": 24.1,
            "mean_difference": -2.7,
            "t_statistic": -3.52,
            "degrees_of_freedom": 55.8,
            "p_value": 0.0009,
            "alpha": 0.05,
            "significant": true,
            "cohens_d": -0.91
        }
    }
    """

    # ============================================================
    # 1. 检查 request
    # ============================================================

    if not isinstance(request, dict):
        raise TypeError("request 必须是 dict")

    data_path = request.get("data_path")

    if not data_path:
        raise ValueError("缺少 data_path")

    params = request.get("params", {})

    if not isinstance(params, dict):
        raise TypeError("params 必须是 dict")

    # ============================================================
    # 2. 获取参数
    # ============================================================

    target_column = params.get("target_column")

    if not target_column:
        raise ValueError("缺少 target_column")

    group_column = params.get("group_column")

    if not group_column:
        raise ValueError("缺少 group_column")

    groups = params.get("groups")

    if not isinstance(groups, list):
        raise TypeError("groups 必须是 array")

    if len(groups) != 2:
        raise ValueError(
            "groups 必须包含且只能包含两个类别"
        )

    if groups[0] == groups[1]:
        raise ValueError(
            "groups 中的两个类别不能相同"
        )

    equal_var = params.get("equal_var", "auto")

    if equal_var not in [
        "auto",
        True,
        False,
        "true",
        "false"
    ]:
        raise ValueError(
            "equal_var 必须是 auto、true 或 false"
        )

    alternative = params.get(
        "alternative",
        "two-sided"
    )

    if alternative not in [
        "two-sided",
        "less",
        "greater"
    ]:
        raise ValueError(
            "alternative 必须是 "
            "two-sided、less 或 greater"
        )

    alpha = params.get("alpha", 0.05)

    if not isinstance(alpha, (int, float)):
        raise TypeError("alpha 必须是数字")

    if alpha <= 0 or alpha >= 1:
        raise ValueError(
            "alpha 必须位于 0 和 1 之间"
        )

    # ============================================================
    # 3. 读取 CSV
    # ============================================================

    try:
        df = pd.read_csv(data_path)

    except FileNotFoundError:
        raise FileNotFoundError(
            f"找不到数据文件: {data_path}"
        )

    except Exception as e:
        raise ValueError(
            f"读取 CSV 文件失败: {str(e)}"
        )

    # ============================================================
    # 4. 检查字段
    # ============================================================

    if target_column not in df.columns:
        raise ValueError(
            f"目标变量不存在: {target_column}"
        )

    if group_column not in df.columns:
        raise ValueError(
            f"分组变量不存在: {group_column}"
        )

    # ============================================================
    # 5. 检查目标变量是否为数值型
    # ============================================================

    if not pd.api.types.is_numeric_dtype(
        df[target_column]
    ):
        raise ValueError(
            f"目标变量 {target_column} 必须是数值型"
        )

    # ============================================================
    # 6. 提取两个组
    # ============================================================

    group1_value = groups[0]
    group2_value = groups[1]

    data1 = df[
        df[group_column] == group1_value
    ][target_column].dropna()

    data2 = df[
        df[group_column] == group2_value
    ][target_column].dropna()

    # ============================================================
    # 7. 检查样本数量
    # ============================================================

    if len(data1) < 2:
        raise ValueError(
            f"组 {group1_value} 的有效样本数不足，"
            "至少需要 2 个样本"
        )

    if len(data2) < 2:
        raise ValueError(
            f"组 {group2_value} 的有效样本数不足，"
            "至少需要 2 个样本"
        )

    # ============================================================
    # 8. 计算两个组的均值
    # ============================================================

    mean1 = data1.mean()
    mean2 = data2.mean()

    mean_difference = mean1 - mean2

    # ============================================================
    # 9. 确定 equal_var
    # ============================================================

    if equal_var == "auto":

        # --------------------------------------------------------
        # Levene 方差齐性检验
        # --------------------------------------------------------

        levene_stat, levene_p = stats.levene(
            data1,
            data2,
            center="median"
        )

        # p >= alpha：
        # 不能拒绝方差相等
        #
        # p < alpha：
        # 认为方差存在显著差异
        if levene_p >= alpha:
            use_equal_var = True
        else:
            use_equal_var = False

    elif equal_var in [True, "true"]:
        use_equal_var = True

    else:
        use_equal_var = False

    # ============================================================
    # 10. 独立样本 t 检验
    # ============================================================

    t_statistic, p_value = stats.ttest_ind(
        data1,
        data2,
        equal_var=use_equal_var,
        alternative=alternative
    )

    # ============================================================
    # 11. 自由度
    # ============================================================

    n1 = len(data1)
    n2 = len(data2)

    var1 = data1.var(ddof=1)
    var2 = data2.var(ddof=1)

    if use_equal_var:

        degrees_of_freedom = (
            n1 + n2 - 2
        )

    else:

        # Welch-Satterthwaite degrees of freedom

        numerator = (
            var1 / n1
            + var2 / n2
        ) ** 2

        denominator = (
            (var1 / n1) ** 2 / (n1 - 1)
            + (var2 / n2) ** 2 / (n2 - 1)
        )

        if denominator == 0:
            degrees_of_freedom = None
        else:
            degrees_of_freedom = (
                numerator / denominator
            )

    # ============================================================
    # 12. Cohen's d
    # ============================================================

    cohens_d = _calculate_cohens_d(
        data1,
        data2,
        use_equal_var
    )

    # ============================================================
    # 13. 判断显著性
    # ============================================================

    significant = p_value < alpha

    # ============================================================
    # 14. 确定测试名称
    # ============================================================

    if use_equal_var:
        test_name = "student_t_test"
    else:
        test_name = "welch_t_test"

    # ============================================================
    # 15. 构造输出
    # ============================================================

    result = {
        "summary": {
            "test": test_name,
            "group_1": _to_python(group1_value),
            "group_2": _to_python(group2_value),
            "mean_1": round(float(mean1), 6),
            "mean_2": round(float(mean2), 6),
            "mean_difference": round(
                float(mean_difference),
                6
            ),
            "t_statistic": round(
                float(t_statistic),
                6
            ),
            "degrees_of_freedom": (
                None
                if degrees_of_freedom is None
                else round(
                    float(degrees_of_freedom),
                    6
                )
            ),
            "p_value": round(
                float(p_value),
                6
            ),
            "alpha": float(alpha),
            "significant": bool(significant),
            "cohens_d": (
                None
                if cohens_d is None
                else round(
                    float(cohens_d),
                    6
                )
            )
        }
    }

    return result