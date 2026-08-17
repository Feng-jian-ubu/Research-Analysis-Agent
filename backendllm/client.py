import os
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

    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=temperature,
    )

    content = response.choices[0].message.content

    if not content:
        raise ValueError("大语言模型未返回有效内容。")

    return content.strip()



