from telesafety_defense.base_factory import OutputDefender


class PassThroughDefender(OutputDefender):
    """No-op defender used for baseline/API-only evaluation."""

    def defend(self, model, messages):
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        return model.chat(messages)
