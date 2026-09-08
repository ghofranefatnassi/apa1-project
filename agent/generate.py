"""
Génère un workflow n8n en JSON à partir d'une description.
Usage :
    python generate.py "Créer un workflow..."
Clé requise : GEMINI_API_KEY
"""

import json
import os
import sys
from pathlib import Path

from google import genai
from google.genai import types

sys.path.append(str(Path(__file__).parent))
from prompt_builder import build_system_prompt

MODEL = "gemma-4-31b-it"
MAX_RETRIES = 2  # nombre de tentatives de re-generation en cas de JSON invalide


class GenerationError(Exception):
    pass


def _extract_json(raw_text: str) -> dict:
    """Nettoie et parse la sortie du modele en JSON. Leve GenerationError si invalide."""
    text = raw_text.strip()
    # Securite : si jamais le modele ajoute des balises markdown malgre la consigne
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise GenerationError(f"Sortie non-JSON ou malformee : {e}\nContenu brut: {raw_text[:500]}")


def generate_workflow(description: str, client: "genai.Client | None" = None) -> dict:
    """
      Génère un workflow n8n à partir d'une description.
      Retourne le workflow ou une erreur si la demande est hors périmètre.
      Lève une erreur si le JSON généré est invalide.
    """
    if client is None:
        client = genai.Client()  # lit GEMINI_API_KEY depuis l'environnement

    system_prompt = build_system_prompt()

    last_error = None
    for attempt in range(1, MAX_RETRIES + 2):
        prompt = description
        # A partir de la 2e tentative, on informe le modele de l'erreur precedente
        if last_error:
            prompt = (
                f"{description}\n\n"
                f"(Note : ta reponse precedente etait invalide : {last_error}. "
                f"Reponds uniquement avec un JSON valide, sans texte autour.)"
            )

        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=2000,
                response_mime_type="application/json",
            ),
        )

        raw_text = response.text or ""

        try:
            parsed = _extract_json(raw_text)
            return parsed
        except GenerationError as e:
            last_error = str(e)
            continue

    raise GenerationError(
        f"Echec de generation apres {MAX_RETRIES + 1} tentatives. Derniere erreur : {last_error}"
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate.py \"<description en langage naturel>\"")
        sys.exit(1)

    description = sys.argv[1]
    try:
        result = generate_workflow(description)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except GenerationError as e:
        print(f"Erreur de generation: {e}", file=sys.stderr)
        sys.exit(1)
