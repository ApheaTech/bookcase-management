from typing import Any, Dict, List, Optional

from llm_adapter import ChatMessage, LLMAdapter


class ReadingPreferenceAgent:
    def __init__(self, adapter: Optional[LLMAdapter] = None):
        self.adapter = adapter or LLMAdapter()

    def analyze(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        profile = self._normalize_payload(payload)
        messages = self._build_messages(profile)

        response = self.adapter.chat(messages=messages)

        return {
            "analysis": response.content,
            "provider": response.provider,
            "model": response.model,
            "input_summary": {
                "book_titles_count": len(profile["book_titles"]),
            },
        }

    def _normalize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        book_titles = payload.get("book_titles") or payload.get("books") or []
        if not isinstance(book_titles, list) or not book_titles:
            raise ValueError("Field 'book_titles' must be a non-empty list")

        normalized_titles: List[str] = []
        for title in book_titles:
            title = str(title).strip()
            if not title:
                raise ValueError("Each item in 'book_titles' must be a non-empty string")
            normalized_titles.append(title)

        return {
            "book_titles": normalized_titles,
            "analysis_goal": str(payload.get("analysis_goal", "")).strip() or "分析用户的阅读偏好",
        }

    def _build_messages(self, profile: Dict[str, Any]) -> List[ChatMessage]:
        system_prompt = (
            "你是一个专业的阅读偏好分析助手。"
            "用户会提供一组书名，请你仅根据这些书名推断这位用户可能的阅读偏好。"
            "请输出一篇中文分析文章，目标长度约 2000 字。"
            "内容需要覆盖以下方面："
            "1. 整体阅读气质与兴趣倾向；"
            "2. 可能偏好的主题、题材和知识领域；"
            "3. 可能偏好的表达风格、叙事方式或信息密度；"
            "4. 从书单中可推断出的认知特征、学习方式或选书标准；"
            "5. 可能不太偏好的内容类型；"
            "6. 后续阅读建议与扩展方向。"
            "请保持分析具体、自然、连贯，不要输出 JSON，不要分点罗列关键词，不要编造读者明确说过的话。"
            "如果书名信息不足以支撑高置信判断，请明确说明这是基于书单的推测。"
        )
        user_prompt = (
            "请根据以下书名列表分析这位用户的阅读偏好，并输出约 2000 字中文分析：\n"
            + "\n".join(f"- {title}" for title in profile["book_titles"])
        )

        return [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt),
        ]
