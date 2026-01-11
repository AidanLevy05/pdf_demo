import requests
import json
import logging

logging.basicConfig(level=logging.INFO)

class ModelClient:
    def __init__(self, base_url="http://127.0.0.1:11434", model="qwen2.5:7b-instruct"):
        self.base_url = base_url
        self.model = model

    def answer(self, question: str, context: str) -> dict:
        prompt = (
            "You must answer using ONLY the context.\n"
            "Return ONLY valid JSON with exactly these keys:\n"
            "quote: an exact substring copied from the context that answers the question\n"
            "answer: a short answer based only on the quote\n"
            "citation: in the form \"sample.pdf p.1\" (use the Source line)\n"
            "\n"
            "Rules:\n"
            "- The quote MUST be copied verbatim from the context.\n"
            "- If you cannot find an exact quote, return ONLY: {\"quote\":\"\",\"answer\":\"I don't know based on the provided PDFs.\",\"citation\":\"\"}\n"
            "- Do not add extra keys. Do not add markdown.\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"QUESTION:\n{question}\n"
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
