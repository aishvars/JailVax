import os 
import litellm
import requests
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import TOGETHER_MODEL_NAMES, LOCAL_MODEL_NAMES, GEMINI_MODEL_NAMES, LITELLM_TEMPLATES, API_KEY_NAMES, Model
from loggers import logger
from common import get_api_key

class LanguageModel():
    def __init__(self, model_name):
        self.model_name = Model(model_name)
    
    def batched_generate(self, prompts_list: list, max_n_tokens: int, temperature: float):
        """
        Generates responses for a batch of prompts using a language model.
        """
        raise NotImplementedError


class VertexAIDirectModel(LanguageModel):
    """
    Calls the Vertex AI Express REST API directly with ?key=API_KEY.
    Bypasses litellm's OAuth/ADC requirement entirely.
    """
    API_MAX_RETRY = 5
    API_RETRY_SLEEP = 10

    def __init__(self, model_name):
        super().__init__(model_name)
        self.api_key = os.environ.get("GOOGLE_API_KEY")
        self.project = os.environ.get("VERTEXAI_PROJECT")
        self.location = os.environ.get("VERTEXAI_LOCATION", "us-central1")
        
        # Extract the bare model name (e.g. "gemini-2.0-flash" from "vertex_ai/gemini-2.0-flash")
        self.vertex_model_name = GEMINI_MODEL_NAMES[self.model_name].replace("vertex_ai/", "")
        
        # Build the endpoint URL
        self.endpoint = (
            f"https://{self.location}-aiplatform.googleapis.com/v1/projects/{self.project}"
            f"/locations/{self.location}/publishers/google/models/{self.vertex_model_name}:generateContent"
        )
        
        self.use_open_source_model = False
        self.post_message = ""
        self.eos_tokens = []
        logger.debug(f"VertexAIDirectModel initialized: {self.vertex_model_name} @ {self.location}")

    def _call_vertex(self, messages, max_n_tokens, temperature, top_p, stop):
        """Make a single request to the Vertex AI REST endpoint."""
        # Convert OpenAI-format messages to Gemini format
        gemini_contents = []
        system_instruction = None
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                system_instruction = content
            elif role == "user":
                gemini_contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                gemini_contents.append({"role": "model", "parts": [{"text": content}]})

        body = {
            "contents": gemini_contents,
            "generationConfig": {
                "maxOutputTokens": max_n_tokens,
                "temperature": temperature,
                "topP": top_p,
            }
        }
        if system_instruction:
            body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        if stop:
            body["generationConfig"]["stopSequences"] = stop

        for attempt in range(self.API_MAX_RETRY):
            try:
                resp = requests.post(
                    f"{self.endpoint}?key={self.api_key}",
                    headers={"Content-Type": "application/json"},
                    json=body,
                    timeout=60
                )
                if resp.status_code == 429:
                    wait = self.API_RETRY_SLEEP * (attempt + 1)
                    logger.warning(f"Rate limited. Retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                
                # Extract text from Gemini response
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    text = "".join(p.get("text", "") for p in parts)
                    return text
                else:
                    logger.warning(f"No candidates in Vertex AI response: {data}")
                    return ""
            except requests.exceptions.HTTPError as e:
                logger.error(f"Vertex AI HTTP error (attempt {attempt+1}): {e}")
                logger.error(f"Response body: {resp.text}")
                if attempt < self.API_MAX_RETRY - 1:
                    time.sleep(self.API_RETRY_SLEEP)
                else:
                    raise
            except Exception as e:
                logger.error(f"Vertex AI error (attempt {attempt+1}): {e}")
                if attempt < self.API_MAX_RETRY - 1:
                    time.sleep(self.API_RETRY_SLEEP)
                else:
                    raise

    def batched_generate(self, convs_list, max_n_tokens, temperature, top_p,
                         extra_eos_tokens=None):
        """Generate responses for a batch of conversations (parallel)."""
        stop = list(extra_eos_tokens) if extra_eos_tokens else None

        responses = []
        with ThreadPoolExecutor(max_workers=min(len(convs_list), 5)) as executor:
            futures = {
                executor.submit(
                    self._call_vertex, conv, max_n_tokens, temperature, top_p, stop
                ): i
                for i, conv in enumerate(convs_list)
            }
            # Collect results in order
            results = [None] * len(convs_list)
            for future in as_completed(futures):
                idx = futures[future]
                results[idx] = future.result()
            responses = results
        
        return responses
    

class APILiteLLM(LanguageModel):
    API_RETRY_SLEEP = 10
    API_ERROR_OUTPUT = "ERROR: API CALL FAILED."
    API_QUERY_SLEEP = 1
    API_MAX_RETRY = 5
    API_TIMEOUT = 20

    def __init__(self, model_name):
        super().__init__(model_name)
        self.api_key = get_api_key(self.model_name)
        self.litellm_model_name = self.get_litellm_model_name(self.model_name)
        litellm.drop_params=True
        self.set_eos_tokens(self.model_name)
        
    def get_litellm_model_name(self, model_name):
        if model_name in TOGETHER_MODEL_NAMES:
            litellm_name = TOGETHER_MODEL_NAMES[model_name]
            self.use_open_source_model = True
        elif model_name in LOCAL_MODEL_NAMES:
            # Local model via Ollama — no API key, no prompt template injection
            litellm_name = LOCAL_MODEL_NAMES[model_name]
            self.use_open_source_model = False
        elif model_name in GEMINI_MODEL_NAMES:
            # This branch should not be reached — Gemini is handled by VertexAIDirectModel
            litellm_name = GEMINI_MODEL_NAMES[model_name]
            self.use_open_source_model = False
        else:
            self.use_open_source_model = False
            litellm_name = model_name.value 
        return litellm_name
    
    def set_eos_tokens(self, model_name):
        if self.use_open_source_model:
            self.eos_tokens = LITELLM_TEMPLATES[model_name]["eos_tokens"]     
        else:
            self.eos_tokens = []

    def _update_prompt_template(self):
        # We manually add the post_message later if we want to seed the model response
        if self.model_name in LITELLM_TEMPLATES:
            litellm.register_prompt_template(
                initial_prompt_value=LITELLM_TEMPLATES[self.model_name]["initial_prompt_value"],
                model=self.litellm_model_name,
                roles=LITELLM_TEMPLATES[self.model_name]["roles"]
            )
            self.post_message = LITELLM_TEMPLATES[self.model_name]["post_message"]
        else:
            self.post_message = ""
        
    
    
    def batched_generate(self, convs_list: list[list[dict]], 
                         max_n_tokens: int, 
                         temperature: float, 
                         top_p: float,
                         extra_eos_tokens: list[str] = None) -> list[str]: 
        
        eos_tokens = self.eos_tokens 

        if extra_eos_tokens:
            eos_tokens.extend(extra_eos_tokens)
        if self.use_open_source_model:
            self._update_prompt_template()
        
        outputs = litellm.batch_completion(
            model=self.litellm_model_name, 
            messages=convs_list,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_n_tokens,
            num_retries=self.API_MAX_RETRY,
            seed=0,
            stop=eos_tokens,
            **({"api_key": self.api_key} if self.api_key is not None else {})
        )
        
        for output in outputs:
            if isinstance(output, Exception):
                logger.error(f"LiteLLM error: {output}")
                raise output
                
        responses = [output["choices"][0]["message"].content for output in outputs]
        return responses
