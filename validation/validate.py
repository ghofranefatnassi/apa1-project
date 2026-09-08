"""
validate.py

Valide un workflow JSON genere en le soumettant a une instance n8n isolee
(sandbox / bac a sable) via l'API REST n8n publique (/api/v1/workflows).

Necessite les variables d'environnement :
  N8N_API_URL   ex: http://localhost:5678
  N8N_API_KEY   cle API generee dans n8n (Settings > API)

Reference API n8n : POST /api/v1/workflows, DELETE /api/v1/workflows/{id}
"""

import os
from dataclasses import dataclass

import requests

N8N_API_URL = os.environ.get("N8N_API_URL", "http://localhost:5678")
N8N_API_KEY = os.environ.get("N8N_API_KEY", "")

HEADERS = {
    "X-N8N-API-KEY": N8N_API_KEY,
    "Content-Type": "application/json",
}


@dataclass
class ValidationResult:
    passed: bool
    stage: str          # "schema" | "creation" | "cleanup" | "ok"
    detail: str
    workflow_id: str | None = None


REQUIRED_TOP_LEVEL_FIELDS = ["name", "nodes", "connections"]
REQUIRED_NODE_FIELDS = ["id", "name", "type", "typeVersion", "position", "parameters"]


def check_schema(workflow: dict) -> ValidationResult:
    """Verification structurelle minimale avant tout appel a l'API n8n."""
    if "error" in workflow:
        return ValidationResult(
            passed=False, stage="schema",
            detail=f"L'agent a signale hors-perimetre: {workflow.get('reason')}"
        )

    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in workflow:
            return ValidationResult(
                passed=False, stage="schema",
                detail=f"Champ racine manquant: '{field}'"
            )

    if not isinstance(workflow["nodes"], list) or len(workflow["nodes"]) == 0:
        return ValidationResult(
            passed=False, stage="schema", detail="'nodes' doit etre une liste non vide"
        )

    for node in workflow["nodes"]:
        for field in REQUIRED_NODE_FIELDS:
            if field not in node:
                return ValidationResult(
                    passed=False, stage="schema",
                    detail=f"Node '{node.get('name', '?')}' : champ manquant '{field}'"
                )

    return ValidationResult(passed=True, stage="schema", detail="OK")


def create_in_sandbox(workflow: dict) -> ValidationResult:
    """
    Tente de creer le workflow dans l'instance n8n sandbox via l'API REST.
    C'est cette etape qui capte les erreurs que la simple verification de
    schema ne peut pas voir (types de node invalides, parametres incoherents
    avec la version du node, etc.).
    """
    # n8n exige que 'active' soit absent ou false a la creation, et que
    # 'settings' soit present.
    payload = {
        "name": workflow.get("name", "Workflow genere"),
        "nodes": workflow["nodes"],
        "connections": workflow.get("connections", {}),
        "settings": workflow.get("settings", {"executionOrder": "v1"}),
    }

    try:
        resp = requests.post(
            f"{N8N_API_URL}/api/v1/workflows",
            headers=HEADERS,
            json=payload,
            timeout=15,
        )
    except requests.RequestException as e:
        return ValidationResult(
            passed=False, stage="creation",
            detail=f"Impossible de joindre l'instance n8n sandbox ({N8N_API_URL}) : {e}"
        )

    if resp.status_code not in (200, 201):
        return ValidationResult(
            passed=False, stage="creation",
            detail=f"n8n a rejete le workflow (HTTP {resp.status_code}): {resp.text[:400]}"
        )

    created = resp.json()
    workflow_id = created.get("id")
    return ValidationResult(
        passed=True, stage="creation", detail="Workflow cree avec succes dans le sandbox",
        workflow_id=workflow_id,
    )


def cleanup(workflow_id: str) -> ValidationResult:
    """Supprime le workflow de test du sandbox pour ne pas le polluer."""
    try:
        resp = requests.delete(
            f"{N8N_API_URL}/api/v1/workflows/{workflow_id}",
            headers=HEADERS,
            timeout=15,
        )
    except requests.RequestException as e:
        return ValidationResult(passed=False, stage="cleanup", detail=str(e))

    if resp.status_code not in (200, 204):
        return ValidationResult(
            passed=False, stage="cleanup",
            detail=f"Echec suppression (HTTP {resp.status_code})"
        )
    return ValidationResult(passed=True, stage="cleanup", detail="OK")


def validate_workflow(workflow: dict, keep_in_sandbox: bool = False) -> ValidationResult:
    """
    Pipeline complet de validation :
      1. Verification de schema (rapide, local)
      2. Creation reelle dans le sandbox n8n (capte les erreurs n8n-side)
      3. Nettoyage (suppression du workflow de test), sauf si keep_in_sandbox=True
    """
    schema_result = check_schema(workflow)
    if not schema_result.passed:
        return schema_result

    creation_result = create_in_sandbox(workflow)
    if not creation_result.passed:
        return creation_result

    if not keep_in_sandbox and creation_result.workflow_id:
        cleanup_result = cleanup(creation_result.workflow_id)
        if not cleanup_result.passed:
            # On ne fait pas echouer la validation globale pour un echec de
            # nettoyage, mais on le signale.
            print(f"[WARN] Nettoyage sandbox echoue: {cleanup_result.detail}")

    return ValidationResult(
        passed=True, stage="ok", detail="Workflow valide et teste avec succes",
        workflow_id=creation_result.workflow_id,
    )
