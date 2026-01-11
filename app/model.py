import requests
import json
import logging

logging.basicConfig(level=logging.INFO)

class ModelClient:
    def __init__(self, base_url="http://127.0.0.1:11434", model="qwen2.5:7b-instruct"):
        self.base_url = base_url
        self.model = model

    def answer(self, question: str, context: str, conversation_history: list = None) -> dict:
        # Build conversation history section if provided
        history_text = ""
        if conversation_history:
            history_text = "CONVERSATION HISTORY:\n"
            for msg in conversation_history[-6:]:  # Last 6 messages (3 turns)
                role = msg["role"].upper()
                content = msg["content"]
                history_text += f"{role}: {content}\n"
            history_text += "\n"

        prompt = (
            "You are an expert assistant helping users understand their documents.\n"
            "Answer the question using ONLY the information in the context below.\n"
            "Provide a comprehensive, detailed answer with explanations.\n"
            "If there is conversation history, use it to understand context and resolve references (like 'it', 'they', 'that').\n\n"
            "Return ONLY valid JSON with exactly these keys:\n"
            "quote: an exact substring from the context that supports your answer\n"
            "answer: a detailed, comprehensive answer (2-4 sentences) based on the context\n"
            "citation: source file and page number in format \"filename.pdf p.X\"\n\n"
            "Rules:\n"
            "- Be thorough and explain the answer clearly\n"
            "- The quote should be verbatim from the context\n"
            "- If you cannot answer, return: {\"quote\":\"\",\"answer\":\"I cannot find this information in the provided documents.\",\"citation\":\"\"}\n"
            "- Do not add extra keys or markdown\n\n"
            f"{history_text}"
            f"CONTEXT:\n{context}\n\n"
            f"CURRENT QUESTION:\n{question}\n\n"
            "JSON:"
        )

        try:
            r = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.0}
                },
                timeout=120,
            )
            r.raise_for_status()
            resp = r.json().get("response", "").strip()

            # Try to parse as JSON
            try:
                return json.loads(resp)
            except json.JSONDecodeError:
                logging.warning(f"LLM returned invalid JSON: {resp}")
                return {
                    "quote": "",
                    "answer": resp,  # Return raw response as answer
                    "citation": "",
                    "raw": resp
                }
        except requests.RequestException as e:
            logging.error(f"LLM request failed: {e}")
            return {
                "quote": "",
                "answer": f"Error: Could not connect to LLM service. {str(e)}",
                "citation": ""
            }
        except Exception as e:
            logging.error(f"Unexpected error in LLM call: {e}")
            return {
                "quote": "",
                "answer": f"Error: {str(e)}",
                "citation": ""
            }
