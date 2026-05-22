from abc import ABC, abstractmethod

class BaseProvider(ABC):
	@abstractmethod
	def generate(self, prompt: str) -> str:
		"""Generate text for the given prompt and return the content string."""
		raise NotImplementedError()
