import os
import sys
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


def _get_client() -> OpenAI:
    api_key = (
        os.getenv("LLM_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )

    base_url = (
        os.getenv("LLM_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
    )

    if not api_key:
        raise ValueError(
            "未配置 LLM_API_KEY 或 OPENAI_API_KEY。"
        )

    client_options: dict[str, Any] = {
        "api_key": api_key,
    }

    if base_url:
        client_options["base_url"] = base_url

    return OpenAI(**client_options)


def _get_model_name() -> str:
    model_name = (
        os.getenv("LLM_MODEL")
        or os.getenv("OPENAI_MODEL")
    )

    if not model_name:
        raise ValueError(
            "未配置 LLM_MODEL 或 OPENAI_MODEL。"
        )

    return model_name


def chat(
    messages: list[dict[str, str]],
    temperature: float = 0.0,
) -> str:
    client = _get_client()
    model_name = _get_model_name()

    stream = client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=temperature,
        stream=True,
    )

    content_parts: list[str] = []

    for chunk in stream:
        # 部分兼容接口会返回不含 choices 的状态或用量分片。
        if not chunk.choices:
            continue

        content = chunk.choices[0].delta.content
        if content:
            content_parts.append(content)

    content = "".join(content_parts).strip()

    if not content:
        raise ValueError("大语言模型未返回有效内容。")

    return content


def main() -> int:
    """发送最小测试请求，检查大语言模型是否可以正常调用。"""
    model_name = os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or "未配置"

    try:
        response = chat(
            [
                {
                    "role": "user",
                    "content": "这是一次连通性测试，请只回复 OK。",
                }
            ]
        )
    except Exception as exc:
        print(f"大语言模型调用失败：{exc}", file=sys.stderr)
        return 1

    print("大语言模型调用成功。")
    print(f"模型：{model_name}")
    print(f"响应：{response}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




