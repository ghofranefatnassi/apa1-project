# APA1 — Compilateur langage naturel → workflow n8n

> Décrire un besoin en une phrase, obtenir un workflow n8n prêt à l'emploi.

## Contexte

Concevoir un workflow n8n suppose aujourd'hui de connaître l'outil en détail, ce qui freine son adoption par les équipes non techniques. Ce projet livre un premier agent capable de traduire une description en langage naturel en un workflow n8n fonctionnel, testé en environnement isolé avant proposition à l'utilisateur.

## Objectifs

1. Définir un périmètre de workflows cibles bien délimité.
2. Développer l'agent de génération du JSON de workflow à partir d'une description en langage naturel.
3. Valider automatiquement le workflow généré dans un environnement n8n isolé avant proposition à l'utilisateur.

## Pipeline

```
Description en langage naturel
        ↓
  agent/generate.py   (Gemma 4 via l'API Gemini)
        ↓
   JSON de workflow n8n
        ↓
 validation/validate.py   (test dans n8n en bac à sable)
        ↓
  Workflow validé + rapport
```

## Périmètre autorisé (4 patterns)

| Pattern | Description |
|---|---|
| **A** | Email reçu → création d'un enregistrement dans l'ERP |
| **B** | Soumission d'un formulaire/webhook → création d'un enregistrement dans l'ERP |
| **C** | Événement ERP → notification (Slack ou email) |
| **D** | Déclenchement planifié → extraction de données ERP → envoi d'un rapport |

Toute description hors de ces 4 patterns — y compris celles qui *ressemblent* structurellement à un pattern autorisé mais visent un système non spécifié — doit être rejetée par l'agent avec `{"error": "out_of_scope", "reason": "..."}`, plutôt que de générer un workflow incorrect.

## Structure du projet

```
apa1-project/
├── templates/              # 4 workflows n8n de référence (few-shot)
│   ├── pattern_a_email_to_erp.json
│   ├── pattern_b_webhook_to_erp.json
│   ├── pattern_c_erp_to_notification.json
│   └── pattern_d_schedule_report.json
├── agent/
│   ├── prompt_builder.py   # construit le prompt système à partir des templates
│   └── generate.py         # appelle Gemma 4, retourne le JSON de workflow
├── validation/
│   └── validate.py         # teste le JSON généré dans n8n (sandbox)
├── tests/
│   ├── test_descriptions.json
│   ├── run_tests.py         # lance tout le jeu de test → report.csv
│   └── report.csv            # généré après exécution
├── .env.example
└── requirements.txt
```

## Environnement technique

- `n8n` — installé nativement (pas de Docker requis)
- `LLM` — Gemma 4 (Google), via l'API Gemini, gratuite
- `API n8n` — utilisée par `validate.py` pour créer/tester/supprimer des workflows
- Environnement n8n isolé (bac à sable) — les tests ne touchent jamais un environnement de production

## Prérequis

- Python 3.10+
- n8n installé (`npm install -g n8n` ou équivalent) — pas besoin de Docker
- Une clé API Gemini gratuite : [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

## Installation

```powershell
git clone <repo>  # ou dézipper le projet
cd apa1-project

python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

1. Copier le fichier d'exemple :
```powershell
copy .env.example .env
```

2. Renseigner `.env` :
```
GEMINI_API_KEY=AIzaSy...votre_cle...

N8N_API_URL=http://localhost:5678
N8N_API_KEY=n8n_api_xxxxxxxx

ERP_BASE_URL=https://your-erpnext-instance.com
SLACK_CHANNEL_ID=C0123456789
REPORT_RECIPIENT_EMAIL=you@example.com
```

3. Charger les variables d'environnement.

   **macOS/Linux (bash) :**
   ```bash
   export $(cat .env | xargs)
   ```

   **Windows (PowerShell)** — la commande ci-dessus ne fonctionne pas sous PowerShell, utiliser à la place :
   ```powershell
   Get-Content .env | ForEach-Object {
       if ($_ -match '^\s*([^#=]+)\s*=\s*(.*)\s*$') {
           [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2])
       }
   }
   ```
   À relancer dans chaque nouvelle fenêtre PowerShell.

   Vérification :
   ```powershell
   echo $env:GEMINI_API_KEY
   ```

## Lancer n8n localement

```powershell
n8n
```

Ouvrir `http://localhost:5678`, créer un compte local, puis **Settings → API → Create API Key** et reporter la clé dans `.env` (`N8N_API_KEY`).

## Utilisation

### Générer un workflow

```powershell
python agent/generate.py "Envoie une notification Slack chaque fois qu'une commande est créée."
```

Retourne un JSON de workflow n8n (nodes + connections) si la description correspond à un pattern autorisé, ou `{"error": "out_of_scope", ...}` sinon.

### Valider un workflow généré (sandbox)

```powershell
python validation/validate.py
```

Crée le workflow dans l'instance n8n locale via son API, vérifie qu'il est accepté, puis le supprime.

### Lancer le jeu de tests complet

```powershell
python tests/run_tests.py
```

Exécute les 15 descriptions de test (12 in-scope + 3 out-of-scope) à travers génération + validation sandbox, et écrit `tests/report.csv`.

**Dernier résultat mesuré :**

```
=== Taux de reussite global : 15/15 (100.0%) ===
  Pattern A            : 3/3 (100.0%)
  Pattern B            : 3/3 (100.0%)
  Pattern C            : 3/3 (100.0%)
  Pattern D            : 3/3 (100.0%)
  Pattern out_of_scope : 3/3 (100.0%)
```

### Test live (bout en bout, avec Slack réel)

Pour aller au-delà de la validation de schéma et tester un scénario réellement exécuté :

1. Créer une app Slack (type "Blank app") sur [api.slack.com/apps](https://api.slack.com/apps), ajouter le scope `chat:write`, installer l'app sur le workspace, copier le token `xoxb-...`.
2. Ajouter ce token comme credential "Slack API" dans n8n.
3. Importer le JSON généré par `generate.py` dans l'éditeur n8n (Import from File), sélectionner le credential Slack et le canal réel sur le node "Notify Slack".
4. Activer le workflow.
5. Simuler l'événement ERP en appelant le webhook manuellement :
```powershell
Invoke-RestMethod -Uri "http://localhost:5678/webhook/erp-order-created" -Method Post -ContentType "application/json" -Body '{"order_id": "1234", "customer_name": "Test Client"}'
```
6. Vérifier que le message apparaît dans le canal Slack.

## Modèle IA utilisé

`gemma-4-31b-it` via l'API Gemini (modifiable dans `agent/generate.py`). Le brief ne spécifie qu'un "LLM" générique — aucun fournisseur n'est imposé.

## Dépannage

| Problème | Cause probable | Solution |
|---|---|---|
| `ValueError: No API key was provided` | Variables d'environnement non chargées | Relancer le script de chargement `.env` (PowerShell) dans la session courante |
| Sortie non-JSON / malformée | Texte ajouté autour du JSON par le modèle | `generate.py` réessaie automatiquement (`MAX_RETRIES = 2`) |
| `validate.py` ne se connecte pas à n8n | n8n non lancé | Lancer `n8n` dans un terminal séparé |
| Faux positif sur un cas hors périmètre | Ambiguïté structurelle non couverte dans le prompt | Ajouter un exemple négatif dans `prompt_builder.py` (voir le cas traité pour "second système" non spécifié) |

## Livrables attendus

- Agent de génération fonctionnel sur le périmètre retenu.
- Jeu de descriptions de test et taux de réussite mesuré (`tests/report.csv`).
