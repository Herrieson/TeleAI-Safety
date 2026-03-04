
from abc import ABC, abstractmethod
class Defender(ABC):
    """Abstract base class for all defenders."""
    
    @abstractmethod
    def defend(self, *args, **kwargs):
        """Abstract method to perform defense."""
        pass


class InputDefender(Defender):
    """Abstract base class for internal defenders that work within the model."""
    
    @abstractmethod
    def defend(self, model, messages):
        """
        Defend method for internal defenders.

        Args:
            model: The model wrapper used by the pipeline.
            messages (str / list): The input messages to be defended.

        Returns:
            list: The defended (processed) input messages.
        """
        pass


class OutputDefender(Defender):
    """Abstract base class for external defenders that work outside the model."""
    
    @abstractmethod
    def defend(self, model, messages):
        pass

class InferenceDefender(Defender):
    """Abstract base class for external defenders that work outside the model."""
    
    @abstractmethod
    def defend(self, model, messages):
        pass

class TrainingDefender(Defender):
    """Abstract base class for external defenders that work outside the model."""
    
    @abstractmethod
    def defend(self, model=None, messages=None):
        pass
