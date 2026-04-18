"""
Minimal conversation template module to replace fastchat.model.get_conversation_template.
This avoids the torch dependency that fastchat requires. Only implements the subset
of the fastchat Conversation API that PAIR uses.
"""


class SimpleConversation:
    """
    Lightweight conversation template that produces OpenAI-format messages.
    Mirrors the fastchat Conversation API used by PAIR:
      - set_system_message(msg)
      - append_message(role, content)
      - update_last_message(content)
      - to_openai_api_messages()
      - .messages  (list of [role, content] pairs)
      - .roles     (tuple of ("user", "assistant"))
      - .name      (template name string)
      - .sep2      (separator, used by llama-2 check in common.py)
    """

    def __init__(self, name: str = "llama-2"):
        self.name = name
        self.system_message: str = ""
        self.messages: list = []          # List of [role, content] pairs
        self.roles: tuple = ("user", "assistant")
        self.sep2: str = " </s><s>"       # llama-2 style; gets stripped in common.py

    def set_system_message(self, system_message: str):
        self.system_message = system_message

    def append_message(self, role: str, content):
        self.messages.append([role, content])

    def update_last_message(self, content: str):
        """Replace the content of the most recently added message."""
        self.messages[-1][1] = content

    def to_openai_api_messages(self) -> list[dict]:
        """
        Convert conversation to a list of OpenAI-format message dicts.
        Roles are normalized to 'user' / 'assistant' / 'system'.
        """
        result = []

        if self.system_message:
            result.append({"role": "system", "content": self.system_message})

        # Map whatever role strings are used to the OpenAI role names
        role_map = {
            self.roles[0]: "user",
            self.roles[1]: "assistant",
            "user": "user",
            "assistant": "assistant",
            "human": "user",
        }

        for role, content in self.messages:
            if content is not None:  # Skip seeded-but-empty assistant turns
                openai_role = role_map.get(role, "user")
                result.append({"role": openai_role, "content": content})

        return result


def get_conversation_template(template_name: str) -> SimpleConversation:
    """
    Drop-in replacement for fastchat.model.get_conversation_template.
    Returns a SimpleConversation initialised with the given template name.
    """
    return SimpleConversation(name=template_name)
