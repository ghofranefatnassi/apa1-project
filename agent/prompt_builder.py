"""
prompt_builder.py
Assemble le prompt systeme few-shot pour l'agent de generation, a partir
des templates JSON de reference definis en Phase 1 (voir /templates).
"""

import json
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

# Ordre fixe pour la reproductibilite du prompt
TEMPLATE_FILES = [
    "pattern_a_email_to_erp.json",
    "pattern_b_webhook_to_erp.json",
    "pattern_c_erp_to_notification.json",
    "pattern_d_schedule_report.json",
]


def load_templates() -> list[dict]:
    """Charge les 4 templates de reference depuis /templates."""
    templates = []
    for filename in TEMPLATE_FILES:
        path = TEMPLATES_DIR / filename
        with open(path, "r", encoding="utf-8") as f:
            templates.append(json.load(f))
    return templates


def build_system_prompt() -> str:
    """
    Construit le prompt systeme contenant :
    - les regles de sortie (JSON n8n valide uniquement)
    - les 4 exemples few-shot (description -> JSON) issus de la Phase 1
    """
    templates = load_templates()

    examples_block = ""
    for t in templates:
        pattern_id = t["meta"]["pattern_id"]
        description = t["meta"]["description_fr"]
        # On retire le champ meta avant de le donner en exemple, il n'est pas
        # attendu dans la sortie finale (uniquement utilise en interne ici).
        clean = {k: v for k, v in t.items() if k != "meta"}
        examples_block += (
            f"\n### Exemple - Pattern {pattern_id}\n"
            f"Description utilisateur : \"{description}\"\n"
            f"JSON attendu :\n```json\n{json.dumps(clean, ensure_ascii=False, indent=2)}\n```\n"
        )

    system_prompt = f"""Tu es un agent qui traduit une description en langage naturel d'un besoin
d'automatisation en un workflow n8n valide, au format JSON exploitable par
l'API n8n (POST /api/v1/workflows).

PERIMETRE AUTORISE (Phase 1) - tu ne dois generer QUE des workflows
correspondant a l'un des 4 patterns suivants :
  A. Email recu -> creation d'un enregistrement dans l'ERP
  B. Soumission d'un formulaire/webhook -> creation d'un enregistrement dans l'ERP
  C. Creation/evenement ERP -> notification (Slack ou email)
  D. Declenchement planifie -> extraction de donnees ERP -> envoi d'un rapport

Si la description ne correspond a AUCUN de ces 4 patterns, ne genere pas de
JSON : reponds uniquement avec l'objet suivant :
{{"error": "out_of_scope", "reason": "<courte explication en francais>"}}

PRECISION SUR LE PERIMETRE - "l'ERP" designe UNIQUEMENT le systeme ERP de
reference utilise dans les 4 exemples ci-dessous (accessible via ERP_BASE_URL,
type Odoo/ERPNext). Une description est HORS PERIMETRE, meme si elle
ressemble structurellement a un pattern autorise, des qu'elle mentionne :
  - un systeme cible non nomme ou generique ("un second systeme", "une autre
    base de donnees", "un autre outil") plutot que l'ERP de reference,
  - une synchronisation entre deux systemes externes (l'ERP n'etant ni la
    source ni la cible unique),
  - une action qui n'est explicitement ni une creation d'enregistrement ERP
    (A/B), ni une notification declenchee par un evenement ERP (C), ni un
    rapport planifie depuis l'ERP (D).
Ne generalise pas un pattern autorise a un systeme non specifie sous pretexte
que la structure (declencheur -> action) se ressemble.

REGLES DE SORTIE :
- Reponds UNIQUEMENT avec un objet JSON valide, sans texte avant ou apres,
  sans balises markdown, sans commentaires.
- Respecte strictement la structure des exemples ci-dessous : champs
  "name", "nodes", "connections", "settings".
- Chaque node doit avoir : id, name, type, typeVersion, position, parameters.
- Adapte les "parameters" (urls, champs, canal Slack, destinataire email,
  frequence) au contenu specifique de la description utilisateur, en te
  basant sur le pattern le plus proche.
- Utilise des noms de nodes explicites et coherents avec les exemples.
- N'invente pas de nouveaux types de nodes n8n : reste sur les types utilises
  dans les exemples (emailReadImap, webhook, httpRequest, set, slack,
  emailSend, scheduleTrigger, code).

EXEMPLES DE REFERENCE (few-shot) :
{examples_block}

### Exemple - Hors perimetre (piege courant)
Description utilisateur : "Quand une commande est payee, mets a jour son statut dans un second systeme."
JSON attendu :
```json
{{"error": "out_of_scope", "reason": "Le systeme cible n'est pas l'ERP de reference mais un 'second systeme' non specifie : ce n'est ni une creation dans l'ERP (A/B), ni une notification depuis l'ERP (C), ni un rapport (D)."}}
```
Ce cas ressemble structurellement au Pattern B (declencheur -> mise a jour)
mais en differe car la cible n'est pas l'ERP de reference : c'est pourquoi il
est hors perimetre malgre l'apparence.

Genere maintenant le JSON pour la description utilisateur fournie, en
suivant exactement ces regles.
"""
    return system_prompt


if __name__ == "__main__":
    # Petit test manuel : affiche le prompt genere
    print(build_system_prompt())