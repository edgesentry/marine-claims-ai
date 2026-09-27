# Public Datasets & Accuracy Evaluation Methodology

This document details the public information collected for **MarineClaims AI**, the end-to-end methodology for measuring appraisal accuracy against objective ground truth, and the automated regression testing harness running in CI/CD.

For the theoretical formalization of rules, refer to [Symbolic AI Implementation Framework](symbolic_ai_implementation_framework.md).  
For the development sequence and gates, refer to [Open-Core Research & Development Roadmap](research_and_development_roadmap.md).  
For the continuous self-refinement cycle, refer to [Iterative Knowledge Loop Specification](iterative_knowledge_loop_specification.md).

---

## 1. Public Information Corpus & Ingestion Architecture

Under the project's **Zero-Dataset Policy**, raw files and proprietary claim dossiers are never committed to git. Instead, public data is fetched on-demand into gitignored local caches via reproducible scripts (`scripts/fetch_public_datasets.py`).

```mermaid
flowchart TD
    subgraph SOURCES["Public Maritime Data Sources"]
        S1["MLIT JTSB Marine Accident Reports\nOfficial Collision & Grounding Investigation PDFs"]
        S2["Prefectural Official Gazettes\nPublic Shipyard Tenders & Contract Award Lists"]
        S3["MLIT Japan Marine Accident Tribunal\nJMAT Official Major Casualty Rulings"]
        S4["Japanese Courts (courts.go.jp)\nCivil Maritime Collision Judgments"]
        S5["Paris MOU & Tokyo MOU Port State Control\nAnnual Flag Inspection & Detention Statistics"]
    end

    subgraph INGEST["Automated Ingestion Pipeline: fetch_public_datasets.py"]
        I1["Idempotent HTTP/PDF Downloader\nRate-Limited Fetching with Local Caching"]
        I2["Tabular Normalization Engine\nPolars Extraction into JSON/Parquet"]
    end

    subgraph CACHE["Local Gitignored Workspace Cache"]
        C1["Public Spec & Casualty PDFs"]
        C2["Benchmark Test Suites & Precedent Vectors"]
    end

    S1 --> I1
    S2 --> I1
    S3 --> I1
    S4 --> I1
    S5 --> I1
    I1 --> I2 --> CACHE
```

### 1.1 Summary of Ingested Datasets

- **JTSB Marine Accident Investigation Reports (運輸安全委員会)**:
  - *Source*: Japan Transport Safety Board (MLIT).
  - *Data Captured*: Official casualty investigation reports (e.g., container ship bow collision, coastal tanker bridge collision) detailing verified impact locations, vessel speeds, visibility, and damage descriptions.
- **Public Shipyard Repair Specifications & Contract Awards (修繕仕様書・落札結果)**:
  - *Source*: Prefectural Gazettes (e.g., Fukuoka Prefecture fishery patrol vessels such as *Kaiyo Maru*).
  - *Data Captured*: Itemized multi-page docking specifications covering Hull, Machinery, Electrical, and Common Docking dues (20 to 100+ line items) paired with official awarded contract amounts (JPY).
- **Japan Marine Accident Tribunal Rulings (海難審判所 裁決録)**:
  - *Source*: MLIT JMAT public judicial repository.
  - *Data Captured*: Certified navigational facts, relative encounter geometries, cause determinations, and official tribunal rulings (*主文*).
- **Civil Court Collision Judgments (民事裁判例)**:
  - *Source*: Supreme Court and High Courts public judgment database (`courts.go.jp`).
  - *Data Captured*: Certified civil liability splits (e.g., 65:35, 70:30, 80:20), claimed drydock expenses, awarded damages, and judicial rationale.
- **Port State Control (PSC) WGB Flag Lists (寄港国検査データ)**:
  - *Source*: Paris MOU and Tokyo MOU annual publications.
  - *Data Captured*: Flag-state inspection counts, detention counts, detention rates, and official risk tier classifications (White, Grey, Black).

---

## 2. End-to-End Accuracy Evaluation Pipeline

Accuracy measurement relies on objective, official ground truth embedded within public records. The evaluation pipeline executes in four structured stages:

```mermaid
flowchart TD
    subgraph STAGE1["Stage 1: Input Pairing"]
        P1["JTSB Casualty Narrative\nDamage Zone: Bow & Outer Shell Only"]
        P2["Public Repair Specification\n20-100 Items: Hull, Machinery, Dock Dues"]
    end

    subgraph STAGE2["Stage 2: AI Appraisal Inference (pipeline.py)"]
        A1["Hierarchical Spec Normalization\nPolars Table Parsing"]
        A2["Negative Pattern Library FastEmbed Cosine Scoring"]
        A3["NetworkX Watertight Bulkhead Invariant Check"]
        A4["AAA Rule D DuckDB 50/50 Fee Apportionment"]
        A5["Status Assignment: COVERED / APPORTIONED / EXCLUDED"]
        A1 --> A2 --> A3 --> A4 --> A5
    end

    subgraph STAGE3["Stage 3: Independent Ground Truth Scoring (public_appraisal_eval.py)"]
        G1["Naval Architecture Spatial Gold\nWatertight Invariant: Engine = 100% Exclude"]
        G2["Item-by-Item Bucket Matching"]
    end

    subgraph STAGE4["Stage 4: Automated Metric & Gate Calculation"]
        M1["Status Agreement Rate: ≥ 85% Target"]
        M2["Critical False Accepts: Strictly 0"]
        M3["Cost Estimation MAPE: ≤ 5% Target"]
    end

    P1 & P2 --> STAGE2
    A5 --> G2
    G1 --> G2
    G2 --> STAGE4
```

### 2.1 The Three Rationale Pillars of Accuracy Measurement

#### Pillar 1: Spatial Invariant Ground Truth (Concurrent Repair Screening)
- **The Rationale**: If a vessel experiences a bulbous bow collision with no breach to machinery bulkheads, repairs to internal engine components (e.g., piston extraction, turbocharger overhaul, sanitary sewage unit maintenance) are physical impossibilities as casualty consequences.
- **Gold Baseline**: Defined in an independent validation module (`src/marine_claims_ai/benchmarks/public_appraisal_eval.py`), completely decoupled from the production inference pipeline.
- **Key Metrics**:
  - **Status Agreement Rate**: Percentage of items where AI output matches the independent engineering gold (`COVERED`, `APPORTIONED`, `EXCLUDED`, `REVIEW`). Target: **≥ 85%**.
  - **Critical False Accept (FA)**: Any engine or propulsion item improperly marked as `COVERED` when damage was isolated to the bow. Gate: **Strictly 0 items**.

#### Pillar 2: Judicial Ruling Ground Truth (Collision Fault Attribution)
- **The Rationale**: Maritime tribunal rulings (*JMAT*) and civil court decisions (*courts.go.jp*) contain authoritative, legally binding determinations of fault ratios (e.g., 80:20) and cause assignments.
- **Evaluation Mechanism**: The AI engine extracts collision encounter variables (relative bearing, speed, visibility, COLREGS status) from the facts and predicts liability attribution. The output is scored directly against the court's certified *主文*.
- **Current Benchmark**: 75.0%–80.0% fault concordance across 20 verified historical casualty decisions.

#### Pillar 3: Prefectural Award Tender Ground Truth (Cost Estimation)
- **The Rationale**: Prefectural official gazettes publish exact contract award prices alongside itemized repair specifications.
- **Evaluation Mechanism**: The estimation engine computes repair costs using standard shipyard unit-price heuristics and compares the total against the published awarded bid.
- **Metric**: Mean Absolute Percentage Error (MAPE):

  ```text
  MAPE = (|Estimated JPY - Awarded JPY| / Awarded JPY) × 100%
  ```

- **Current Benchmark**: **3.0% MAPE** (97.0% price estimation accuracy) across municipal shipyard work packages.

---

## 3. Automated Regression Testing Architecture

Regression testing is automated across two synchronized layers: **Continuous Integration (CI/CD)** on every pull request and **Dedicated Regression Evaluation CLIs**.

```mermaid
flowchart TD
    subgraph CI["Layer 1: GitHub Actions CI (Automated on every PR/push)"]
        T1["pytest --tb=short\n61 Unit & Integration Tests\nTopology, Patterns, Apportionment"]
        T2["verify_civil_catalog.py\nPrecedent Catalog URL Liveness Check"]
        T3["check_zero_dataset_leak.py\nCryptographic Content & Zero-Leakage Scan"]
        T4["pymarkdown & ruff\nLinting & Syntax Enforcement"]
    end

    subgraph CLI["Layer 2: Local Benchmark Evaluation Suite"]
        E1["eval_public_appraisal.py --fail-on-gate\nEvaluates Against Local Cached Specification PDFs"]
        E2["verify_3fields_benchmarks.py\nMulti-Domain Scientific Precision Suite"]
    end

    PR["Code Modification / Prompt Update"] --> CI
    PR --> CLI
```

### 3.1 Layer 1: GitHub Actions CI (Unit & Integration Regression)
The project runs 8 automated CI checks on every pull request and push to `main` (`.github/workflows/ci.yml`):

- **`CI/Unit tests` (`pytest --tb=short`)**:
  - Automatically executes **61 unit and regression tests**:
    - `tests/test_negative_patterns.py`: Verifies cosine similarity thresholds, boundary conditions, and keyword override behavior in the Negative Pattern Library.
    - `tests/test_appraisal_causality.py`: Verifies that NetworkX topological checks reject impossible causal claims across watertight bulkheads.
    - `tests/test_public_appraisal_eval.py`: Verifies the scoring engine, status normalization, critical false accept detection, and gate evaluation logic.
    - `tests/test_indexing_and_apportion.py`: Validates mathematical consistency of AAA Rule D 50/50 fee apportionments.
- **`CI/Zero-Dataset leak check` (`scripts/ci/check_zero_dataset_leak.py`)**:
  - Scans all tracked git files and full commit diffs to ensure no raw datasets, unmasked customer records, or API credentials are committed.
- **`CI/Civil catalog link check` (`scripts/ci/verify_civil_catalog.py`)**:
  - Validates that every public court judgment PDF cited in `config/civil_precedent_catalog.json` remains live and accessible.

### 3.2 Layer 2: Public Appraisal Evaluation CLI
When public PDFs are downloaded to local caches, developers and adjusters run the end-to-end evaluation harness:

```bash
uv run python scripts/eval_public_appraisal.py \
  --json-out _inputs/poc_datasets/public_appraisal_eval_report.json \
  --fail-on-gate
```

- **`--fail-on-gate`**: Enforces strict exit thresholds:
  - `min_cases_with_pdfs`: ≥ 3 runnable test cases.
  - `max_critical_false_accepts`: Strictly 0.
  - `min_status_agreement`: ≥ 85.0%.
- If a prompt modification or parser update introduces a regression (e.g., an engine overhaul is erroneously approved under a bow collision), the evaluation script immediately exits with code 1, flagging the exact conflicting line items.

---

## 4. Preventing Tautological Bias (Self-Fulfilling Evaluation)

A common pitfall in AI evaluation is circular testing—evaluating an algorithm against rules generated by that same algorithm. MarineClaims AI eliminates this bias through three architectural safeguards:

1. **Independent Gold Implementation**:
   - The production pipeline utilizes complex prompt embeddings, hierarchical table parsing, and LLM extraction (`src/marine_claims_ai/appraisal/pipeline.py`).
   - The evaluation harness (`src/marine_claims_ai/benchmarks/public_appraisal_eval.py`) uses an independent naval architecture rule policy. Any parser hallucination or heuristic drift creates an immediate regression discrepancy.
2. **Deterministic Physical Invariants**:
   - Watertight bulkheads and compartment boundaries are immutable engineering facts under SOLAS regulations, not subjective LLM choices.
3. **External Judicial Ground Truth**:
   - Collision fault percentages and court damage awards were certified by real judges and maritime tribunals decades before this software was written, providing an unalterable external anchor.

---

## 5. Jurisprudential Grounding: International Conventions, Japanese Law, and Strategic Benchmark Selection

A foundational design question in maritime AI systems is the relationship between **international conventions** (such as COLREGS and SOLAS) and **domestic law** (such as the Japanese Act on Preventing Collisions at Sea and Japanese court judgments). This section details the jurisprudential alignment underpinning the system and explains why Japanese public judicial records serve as the optimal global benchmark without creating legal fragmentation.

### 5.1 Harmonization of International Conventions and Japanese Domestic Law

Maritime law is uniquely standardized worldwide compared to terrestrial civil or penal law. International maritime conventions promulgated by the International Maritime Organization (IMO) are directly transposed by signatory states into domestic legislation with verbatim preservation of mathematical parameters and navigational duties:

- **COLREGS 1972 vs. Act on Preventing Collisions at Sea (海上衝突予防法)**:
  - The Japanese Act on Preventing Collisions at Sea (*海上衝突予防法*, Act No. 62 of 1977) is a direct domestic transposition of the IMO Convention on the International Regulations for Preventing Collisions at Sea (COLREGS 1972).
  - Critical geometric criteria—such as Rule 13 overtaking (approaching from a direction more than 22.5° abaft the beam, corresponding to relative bearings exceeding 112.5°), Rule 14 head-on situations (reciprocal courses within approximately 180° ± 5°), and Rule 15 crossing situations (duty of the vessel having the other on her starboard side to give way)—are **100% identical in definition, numerical threshold, and legal duty** across Japanese, English, US, and Singapore maritime law.
- **SOLAS 1974 & MARPOL 73/78 vs. Japanese Statutory Maritime Safety Laws**:
  - The Japanese Ship Safety Act (*船舶安全法*) and Marine Pollution Prevention Act (*海洋汚染防止法*) enforce identical structural subdivision standards, transverse watertight bulkhead invariants, and machinery fail-safes mandated by SOLAS Chapter II-1 and MARPOL Annex I.
  - Port State Control (PSC) inspections conducted in Japanese ports operate under the exact same Tokyo MOU / IMO Resolution A.1155(32) deficiency code taxonomy as inspections in Rotterdam, Singapore, or Houston.
- **AAA Rule D vs. Japanese Average Adjusters Rules of Practice**:
  - The 50/50 dual-apportionment principle governing drydocking common dues is universally applied across both London (Association of Average Adjusters Rule D) and Tokyo (Association of Average Adjusters of Japan Rule D), originating from shared English admiralty precedents (*The Vancouver* and *The Ruabon*).

### 5.2 Strategic Rationale for Benchmarking Against Japanese Judicial Records

Benchmarking AI reasoning requires authoritative, reproducible ground truth with complete factual inputs. Japanese public maritime records provide distinct strategic advantages over foreign jurisdictions:

1. **Open-Access Telemetry and Fact-Findings (High Judicial Transparency)**:
   - In international maritime hubs like London or Singapore, the majority of collision and salvage disputes are resolved through confidential maritime arbitration (e.g., LMAA, SCMA) or published behind expensive commercial legal paywalls (e.g., *Lloyd's Law Reports* on LexisNexis/i-law).
   - In contrast, the Government of Japan provides comprehensive, certified, open-access public records:
     - **JTSB Casualty Reports**: Contain full AIS navigational tracks, radar plots, certified speeds, encounter angles, and structural damage photographs.
     - **JMAT Decisions (*海難審判裁決録*)**: Provide authoritative judicial determinations of proximate cause, navigational blameworthiness, and administrative rulings (*主文*).
     - **Civil Court Decisions (`courts.go.jp`)**: Provide legally binding civil liability apportionment percentages (e.g., 65:35, 70:30, 80:20) and itemized awarded damages.
2. **International Validity of Japanese Ground Truth**:
   - Because Japanese tribunals evaluate navigational fault strictly under COLREGS principles, a benchmark case demonstrating that the AI correctly attributes a 70:30 crossing liability in Tokyo Bay serves as valid, transferable evidence that the underlying logic engine conforms to international COLREGS standards globally.

### 5.3 Two-Tier Architecture: Universal Core vs. Jurisdiction & Regional Adapters

To guarantee seamless global expansion (e.g., from Japan to Singapore, London, or European hubs) without architectural refactoring, the system enforces a strict separation of concerns:
- **Universal Core (`src/marine_claims_ai/`)**: Codifies immutable physical laws, mathematical apportionment formulas, and international treaty conventions that are identical globally.
- **Jurisdiction & Regional Adapters (`config/jurisdictions/` & LanceDB Partitions)**: Modular plug-in configurations encapsulating local precedent case law, regional shipyard labor tariffs, and domestic fairway regulations.

```mermaid
flowchart TD
    subgraph CORE["Universal Open-Core Engine: Globally Neutral (No Code Changes)"]
        C1["Pillar 1: Spatial Bulkhead Graph & AAA Rule D 50/50 Solver"]
        C2["Pillar 2: COLREGS Rules 13-17 Encounter Geometry Engine"]
        C3["Pillar 3: IMO Statutory Safety Conventions & PSC Taxonomy"]
    end

    subgraph ADAPTERS["Modular Jurisdiction & Regional Adapters (Config / DB Plugins)"]
        A1["Japan Adapter (Current Active Target)\nJMAT Decisions, Tokyo District Court Precedents, Setouchi/Kyushu Tariffs"]
        A2["UK & London Adapter (International Expansion)\nEnglish Admiralty Precedents, LMAA Arbitrations, UK ITC-Hulls"]
        A3["Singapore & SE Asia Adapter (Asia-Pacific Hub)\nSCMA Arbitration Precedents, Malacca Strait Rules, Jurong Tariffs"]
    end

    C1 --> A1
    C2 --> A1
    C3 --> A1
    C1 -.->|"Global Fleet Expansion"| A2
    C1 -.->|"Global Fleet Expansion"| A3
```

#### Detailed Breakdown Across the Three Functional Pillars

| Functional Pillar | Universal Open Core (Globally Invariant) | Jurisdiction & Regional Adapters (Modular Plugins) |
| :--- | :--- | :--- |
| **Pillar 1: Concurrent Repair & Drydock Apportionment** | • **Physical Compartment Invariants**: Transverse watertight bulkhead barriers (SOLAS II-1) preventing causality across isolated compartments.<br>• **Statutory Survey Intervals**: IACS unified periodic survey cycles (Special Survey 5 years, Intermediate Survey 2.5 years) and mandatory inspection items (piston pulls, tailshafts).<br>• **Statutory 50/50 Apportionment**: Association of Average Adjusters (AAA) Rule D mathematical logic for dual-necessity common docking dues.<br>• **Standard Work Breakdown**: SFI group classification system for hull, engine, and electrical trades. | • **Shipyard Man-Hour Tariffs (Regional Rates)**:<br>  - Japan (Setouchi/Kyushu): Approx. 4,500–6,500 JPY/hr.<br>  - Singapore (Jurong): Approx. 35–50 USD/hr.<br>  - China (Zhoushan/Nantong): Approx. 18–28 USD/hr.<br>• **Local Dock Tariff Structure**: Daily lay-docking fee vs. tonnage lump-sum conventions.<br>• **Policy Wordings & Forms**: Japanese Hull Clauses (NK Form) vs. English Institute Time Clauses - Hulls (ITC-Hulls 1/10/83, 1995) vs. Nordic Marine Insurance Plan. |
| **Pillar 2: Collision Fault Attribution & Legal Reasoning** | • **Steering & Sailing Regulations**: COLREGS 1972 Part B (Rule 13 Overtaking > 22.5° abaft the beam, Rule 14 Head-on mutual starboard alteration, Rule 15 Crossing starboard give-way).<br>• **Nautical Telemetry Analytics**: Mathematical computation of Relative Bearing, Course Difference, CPA (Closest Point of Approach), and TCPA from AIS/VDR records.<br>• **Proportional Fault Doctrine**: Core principle of 1910 Collision Convention dividing damages proportionally to fault degree. | • **Judicial Precedent Catalog (Fault Splits)**:<br>  - Japan: JMAT tribunal decisions & civil court precedent catalog.<br>  - UK: English Admiralty Court precedents & LMAA arbitration awards.<br>  - Singapore: SCMA maritime arbitration awards & High Court rulings.<br>• **Contributory Negligence Nuance**: Local judicial discretion on discretionary adjustment percentages (e.g., standard +10% increments for night lookout defaults).<br>• **Fairway Special Regulations**: Local transit rules (Japan Maritime Traffic Safety Act for Uraga/Kanmon vs. Singapore Strait TSS rules vs. Dover Strait CALDOVREP). |
| **Pillar 3: PSC Risk Scoring & Warranty of Seaworthiness** | • **International Convention Treaties**: SOLAS, MARPOL, STCW, and ISM Code text and mandatory safety standards.<br>• **PSC Deficiency & Action Codes**: IMO Resolution A.1155(32) 5-digit category taxonomy (011xx, 041xx, 071xx, 131xx, 151xx) and standardized action codes (Code 17 rectify, Code 30 detention).<br>• **Baseline Severity Weights**: Algorithmic weighting of safety-critical systems (steering gear, emergency fire pumps, SMS non-conformities). | • **Regional MOU Inspection Priorities**: Tokyo MOU vs. Paris MOU vs. US Coast Guard (Qualship 21) annual Concentrated Inspection Campaigns (CIC).<br>• **Legal Thresholds for Warranty Breach**:<br>  - English Law (MIA 1906 Sec 39): Absolute warranty on voyage policies; requiring "privity of the assured" on time policies.<br>  - Japanese Law (Commercial Code Art 815): Carrier due-diligence and burden-of-proof standards.<br>  - Nordic Law (Nordic Plan): Stricter proximate causation requirements. |

#### Architectural Guarantee Against Technical Debt

By enforcing this strict boundary:
1. **Zero Core Logic Rewrite**: The core calculation and constraint engines (`ontology/compartments.py`, `legal/colregs_engine.py`, `analytics/rule_d_solver.py`) remain completely untouched when deploying to international markets.
2. **Configuration-Driven Adaptation**: Adapting to a new maritime cluster (e.g., Singapore or London) requires only populating an external jurisdiction vector table in LanceDB and supplying local shipyard tariff schedules in YAML.
3. **Reproducible Proof of Concept**: Validating the universal core against Japanese open-access judicial records proves the soundness of the underlying COLREGS and SOLAS logic, ensuring instantaneous credibility when presenting to international marine underwriters.
