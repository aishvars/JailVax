from enum import Enum
VICUNA_PATH = "/home/pchao/vicuna-13b-v1.5"
LLAMA_PATH = "/home/pchao/Llama-2-7b-chat-hf"

ATTACK_TEMP = 1
TARGET_TEMP = 0
ATTACK_TOP_P = 0.9
TARGET_TOP_P = 1


## MODEL PARAMETERS ##
class Model(Enum):
    vicuna = "vicuna-13b-v1.5"
    llama_2 = "llama-2-7b-chat-hf"
    gpt_3_5 = "gpt-3.5-turbo-1106"
    gpt_4 = "gpt-4-0125-preview"
    claude_1 = "claude-instant-1.2"
    claude_2 = "claude-2.1"
    gemini = "gemini-pro"
    gemini_flash = "gemini-2.0-flash"       # Google Gemini 2.0 Flash (fast & cheap)
    gemini_pro_2 = "gemini-1.5-pro"         # Google Gemini 1.5 Pro (more capable)
    gemini_flash_lite = "gemini-2.5-flash-lite"  # Gemini 2.5 Flash Lite (Vertex Express)
    gemini_2_5_flash = "gemini-2.5-flash"
    mixtral = "mixtral"
    ollama = "ollama"  # Local Ollama (llama3.2:1b via localhost:11434)

MODEL_NAMES = [model.value for model in Model]


HF_MODEL_NAMES: dict[Model, str] = {
    Model.llama_2: "meta-llama/Llama-2-7b-chat-hf",
    Model.vicuna: "lmsys/vicuna-13b-v1.5",
    Model.mixtral: "mistralai/Mixtral-8x7B-Instruct-v0.1"
}

TOGETHER_MODEL_NAMES: dict[Model, str] = {
    Model.llama_2: "together_ai/togethercomputer/llama-2-7b-chat",
    Model.vicuna: "together_ai/lmsys/vicuna-13b-v1.5",
    Model.mixtral: "together_ai/mistralai/Mixtral-8x7B-Instruct-v0.1"
}

# Local models served via Ollama (routes to http://localhost:11434)
LOCAL_MODEL_NAMES: dict[Model, str] = {
    Model.ollama: "ollama/llama3.2:1b"
}

# Gemini models served via Vertex AI (requires GOOGLE_API_KEY + VERTEXAI_PROJECT)
GEMINI_MODEL_NAMES: dict[Model, str] = {
    Model.gemini_flash: "vertex_ai/gemini-2.0-flash",
    Model.gemini_pro_2: "vertex_ai/gemini-1.5-pro",
    Model.gemini_flash_lite: "vertex_ai/gemini-2.5-flash-lite",
    Model.gemini_2_5_flash: "vertex_ai/gemini-2.5-flash",
}

FASTCHAT_TEMPLATE_NAMES: dict[Model, str] = {
    Model.gpt_3_5: "gpt-3.5-turbo",
    Model.gpt_4: "gpt-4",
    Model.claude_1: "claude-instant-1.2",
    Model.claude_2: "claude-2.1",
    Model.gemini: "gemini-pro",
    Model.gemini_flash: "gemini-pro",           # Reuse gemini template
    Model.gemini_pro_2: "gemini-pro",           # Reuse gemini template
    Model.gemini_flash_lite: "gemini-pro",      # Reuse gemini template
    Model.gemini_2_5_flash: "gemini-pro",
    Model.vicuna: "vicuna_v1.1",
    Model.llama_2: "llama-2-7b-chat-hf",
    Model.mixtral: "mixtral",
    Model.ollama: "llama-2",  # Closest fastchat template for llama3.2
}

API_KEY_NAMES: dict[Model, str] = {
    Model.gpt_3_5:     "OPENAI_API_KEY",
    Model.gpt_4:       "OPENAI_API_KEY",
    Model.claude_1:    "ANTHROPIC_API_KEY",
    Model.claude_2:    "ANTHROPIC_API_KEY",
    Model.gemini:      "GOOGLE_API_KEY",
    Model.gemini_flash:     "GOOGLE_API_KEY",
    Model.gemini_pro_2:     "GOOGLE_API_KEY",
    Model.gemini_flash_lite:"GOOGLE_API_KEY",
    Model.gemini_2_5_flash: "GOOGLE_API_KEY",
    Model.vicuna:      "TOGETHER_API_KEY",
    Model.llama_2:     "TOGETHER_API_KEY",
    Model.mixtral:     "TOGETHER_API_KEY",
    Model.ollama:      None,  # No API key needed for local Ollama
}

LITELLM_TEMPLATES: dict[Model, dict] = {
    Model.vicuna: {"roles":{
                    "system": {"pre_message": "", "post_message": " "},
                    "user": {"pre_message": "USER: ", "post_message": " ASSISTANT:"},
                    "assistant": {
                        "pre_message": "",
                        "post_message": "",
                    },
                },
                "post_message":"</s>",
                "initial_prompt_value" : "",
                "eos_tokens": ["</s>"]         
                },
    Model.llama_2: {"roles":{
                    "system": {"pre_message": "[INST] <<SYS>>\n", "post_message": "\n<</SYS>>\n\n"},
                    "user": {"pre_message": "", "post_message": " [/INST]"},
                    "assistant": {"pre_message": "", "post_message": ""},
                },
                "post_message" : " </s><s>",
                "initial_prompt_value" : "",
                "eos_tokens" :  ["</s>", "[/INST]"]  
            },
    Model.mixtral: {"roles":{
                    "system": {
                        "pre_message": "[INST] ",
                        "post_message": " [/INST]"
                    },
                    "user": { 
                        "pre_message": "[INST] ",
                        "post_message": " [/INST]"
                    }, 
                    "assistant": {
                        "pre_message": " ",
                        "post_message": "",
                    }
                },
                "post_message": "</s>",
                "initial_prompt_value" : "<s>",
                "eos_tokens": ["</s>", "[/INST]"]
    }
}