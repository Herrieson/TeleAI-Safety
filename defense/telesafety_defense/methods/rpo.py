# telesafety_defense/methods/rpo.py

import os
from telesafety_defense.base_factory import InputDefender

try:
    from loguru import logger
except ImportError:
    import logging

    class _StdLoggerAdapter:
        def __init__(self, name: str):
            self._logger = logging.getLogger(name)

        @staticmethod
        def _format(msg, *args):
            if not args:
                return msg
            try:
                return msg.format(*args)
            except Exception:
                return f"{msg} | args={args}"

        def info(self, msg, *args):
            self._logger.info(self._format(msg, *args))

        def warning(self, msg, *args):
            self._logger.warning(self._format(msg, *args))

        def error(self, msg, *args):
            self._logger.error(self._format(msg, *args))

    logger = _StdLoggerAdapter(__name__)

class RPODefender(InputDefender):
    """
    RPO 防御器。
    在推理时，它加载一个预先优化好的 RPO 后缀，并将其附加到用户输入的末尾。
    """
    def __init__(
        self,
        model=None,
        tokenizer=None,
        model_name="unknown-model",
        rpo_suffix_path=None,
        rpo_suffix=None,
        **kwargs,
    ):
        """
        初始化 RPO 防御器。
        """
        self.model = model
        self.tokenizer = tokenizer
        self.model_name = model_name

        if not rpo_suffix_path:
            rpo_suffix_path = kwargs.get("rpo_suffix_path")
        if not rpo_suffix:
            rpo_suffix = kwargs.get("rpo_suffix")

        if isinstance(rpo_suffix, str) and rpo_suffix.strip():
            self.rpo_suffix = rpo_suffix.strip()
        elif isinstance(rpo_suffix_path, str) and rpo_suffix_path.strip():
            if not os.path.exists(rpo_suffix_path):
                raise ValueError(f"RPO suffix file not found at path: {rpo_suffix_path}")
            with open(rpo_suffix_path, "r", encoding="utf-8") as f:
                self.rpo_suffix = f.read().strip()
        else:
            self.rpo_suffix = (
                r":}</'])language seems scary-----------}] estimation >>begin &=&pgf degli ({\ $|\textwidthAI NOTE:"
            )

        logger.info("RPODefender initialized.")
        logger.info(f"Loaded RPO suffix: '{self.rpo_suffix}'")

    def defend(self, model, messages):
        """
        执行 RPO 防御。将 RPO 后缀附加到最新的用户消息中。
        
        Args:
            model: 模型对象
            messages: 输入消息，可以是字符串或消息列表
        
        Returns:
            修改后的消息列表 (注意：RPO 只修改输入，不生成最终回复)
        """
        if isinstance(messages, str):
            # 如果输入是字符串，直接附加
            return f"{messages} {self.rpo_suffix}"
        
        elif isinstance(messages, list) and messages:
            # 如果是消息列表，附加到最后一个用户消息的 content 中
            # 创建一个副本以避免修改原始列表
            modified_messages = [msg.copy() for msg in messages]
            # 找到最后一个角色为 'user' 的消息
            for i in range(len(modified_messages) - 1, -1, -1):
                if modified_messages[i]['role'] == 'user':
                    modified_messages[i]['content'] = f"{modified_messages[i]['content']} {self.rpo_suffix}"
                    # print(f"Modified user message: {modified_messages[i]['content']}")
                    break
            return modified_messages
        
        else:
            # 对于不支持的格式，返回原始输入
            return messages
