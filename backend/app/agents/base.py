from abc import ABC, abstractmethod

from app.services.ai_provider_chain import AIProviderChain


class BaseAgent(ABC):
    def __init__(self):
        self.provider = "openai"
        self.llm = AIProviderChain()
        self.model = self.llm.model
        self.has_ai = self.llm.available()

        # Backward-compatible alias for agents that still use the historical name.
        self.gemini = self.llm
        self.verify_model = self.llm.verify_model

    @abstractmethod
    async def run(self, **kwargs):
        pass
