# Direct Democracy Ca — Problem Categories

> **Document purpose:** This is the canonical reference for the platform's category taxonomy.
> It defines the fixed list of main categories, the rules governing how they work, and the
> seed subcategories that will be pre-loaded at launch.
>
> **Who uses this document:**
> - Developers — to build and update `backend/config/categories.py`
> - Claude Code — to understand the category system before touching any labeling, feed, or proposal code
> - Future team members — to understand why the taxonomy is shaped the way it is
>
> **Status:** 🟡 In Progress — categories not yet finalized

---

## How the Category System Works

*(Brief explanation so anyone reading this cold understands the architecture before seeing the list.)*

**Main categories** are broad topic buckets. The platform controls this list. It grows only through the democratic proposal and approval system — citizens propose, communities vote. The platform owner controls the seed list at launch.

**Subcategories are umbrella problems.** Every subcategory is an umbrella problem. They are the same thing. When a post is labeled, it is assigned to a main category and a subcategory/umbrella simultaneously — one action, not two.

**The AI's role** is to sort posts into the closest matching existing category and subcategory. The AI never creates new subcategories. If no matching subcategory exists, the AI assigns to the main category only and flags for human review.

**The community's role** is to propose and vote on new subcategories (and, rarely, new main categories) through the democratic proposal system.

---

## Design Principles for This List

*(Decisions made about how to construct the category list — record the reasoning here so future decisions stay consistent.)*

- [ ] **Principle 1:** *(e.g. Categories should map to government agency jurisdictions where possible, so pressure can be routed to the right body)*
- [ ] **Principle 2:** *(e.g. No category should be so broad it becomes a catch-all — if everything fits, nothing is organized)*
- [ ] **Principle 3:** *(e.g. Categories should be named from a citizen's perspective, not a bureaucrat's)*
- [ ] **Principle 4:** *(add more as decided)*

---

## Open Design Decisions

*(Questions that must be answered before this document is finalized and the list is locked.)*

- [ ] What is the final number of seed main categories? (current placeholder: 10)
- [ ] Is the main category list truly fixed at launch, or can the platform owner add categories outside the proposal system in the early days?
- [ ] Should categories map to government agency jurisdictions, or to how citizens naturally think about problems?
- [ ] Are there any California-specific categories that don't exist in other states? (e.g. wildfire, water rights, earthquake preparedness)
- [ ] How granular should the seed subcategory list be at launch? (Too many: overwhelming. Too few: nothing fits and the proposal system gets flooded.)
- [ ] *(Add more open questions as they come up)*

---

## Main Categories — Seed List

> **Instructions for filling this in:**
> For each main category, provide: a name, a one-sentence plain-English description of what belongs here,
> the government bodies typically responsible, and the seed subcategories to pre-load at launch.
> Seed subcategories become the first umbrella problems in the system.

---

### 1. [Category Name]

**Description:** *(One sentence. What kinds of problems belong here? Written from a citizen's perspective.)*

**Typically responsible government bodies:** *(e.g. City Public Works, Caltrans, County DPW)*

**What does NOT belong here:** *(Boundary cases that might be confused with this category — where do they actually go?)*

**Seed subcategories / umbrella problems at launch:**
| Subcategory Name | Description | Governance Levels |
|-----------------|-------------|-------------------|
| *(e.g. Pothole and Road Damage)* | *(one line)* | *(City / County / State)* |
| | | |
| | | |

---

### 2. [Category Name]

**Description:**

**Typically responsible government bodies:**

**What does NOT belong here:**

**Seed subcategories / umbrella problems at launch:**
| Subcategory Name | Description | Governance Levels |
|-----------------|-------------|-------------------|
| | | |
| | | |

---

### 3. [Category Name]

**Description:**

**Typically responsible government bodies:**

**What does NOT belong here:**

**Seed subcategories / umbrella problems at launch:**
| Subcategory Name | Description | Governance Levels |
|-----------------|-------------|-------------------|
| | | |
| | | |

---

### 4. [Category Name]

**Description:**

**Typically responsible government bodies:**

**What does NOT belong here:**

**Seed subcategories / umbrella problems at launch:**
| Subcategory Name | Description | Governance Levels |
|-----------------|-------------|-------------------|
| | | |
| | | |

---

### 5. [Category Name]

**Description:**

**Typically responsible government bodies:**

**What does NOT belong here:**

**Seed subcategories / umbrella problems at launch:**
| Subcategory Name | Description | Governance Levels |
|-----------------|-------------|-------------------|
| | | |
| | | |

---

### 6. [Category Name]

**Description:**

**Typically responsible government bodies:**

**What does NOT belong here:**

**Seed subcategories / umbrella problems at launch:**
| Subcategory Name | Description | Governance Levels |
|-----------------|-------------|-------------------|
| | | |
| | | |

---

### 7. [Category Name]

**Description:**

**Typically responsible government bodies:**

**What does NOT belong here:**

**Seed subcategories / umbrella problems at launch:**
| Subcategory Name | Description | Governance Levels |
|-----------------|-------------|-------------------|
| | | |
| | | |

---

### 8. [Category Name]

**Description:**

**Typically responsible government bodies:**

**What does NOT belong here:**

**Seed subcategories / umbrella problems at launch:**
| Subcategory Name | Description | Governance Levels |
|-----------------|-------------|-------------------|
| | | |
| | | |

---

### 9. [Category Name]

**Description:**

**Typically responsible government bodies:**

**What does NOT belong here:**

**Seed subcategories / umbrella problems at launch:**
| Subcategory Name | Description | Governance Levels |
|-----------------|-------------|-------------------|
| | | |
| | | |

---

### 10. [Category Name]

**Description:**

**Typically responsible government bodies:**

**What does NOT belong here:**

**Seed subcategories / umbrella problems at launch:**
| Subcategory Name | Description | Governance Levels |
|-----------------|-------------|-------------------|
| | | |
| | | |

---

## Edge Cases and Boundary Rules

*(Record any categorization decisions that were tricky or non-obvious, so future decisions stay consistent.)*

| Scenario | Decision | Reasoning |
|----------|----------|-----------|
| *(e.g. A post about a broken streetlight — Infrastructure or Public Safety?)* | *(e.g. Infrastructure)* | *(Streetlights are maintained by Public Works, not law enforcement)* |
| | | |
| | | |

---

## What Happens in Code

*(A plain-English summary of how this list is used in the backend, so future developers understand the intent.)*

- `backend/config/categories.py` holds the final list from this document
- The AI labeler reads this file and must choose a main category from it — no free text
- The AI then assigns to the closest approved subcategory/umbrella within that main category
- If no subcategories exist for a main category yet, the AI assigns to the main category only and sets a `pending_subcategory_review` flag
- The seed subcategories in this document are inserted into the database at launch via a seeding script, not raw SQL

---

## Change Log

| Date | Change | Reason |
|------|--------|--------|
| *(date)* | Document created | Initial template |
| | | |

---

*Status: 🟡 In Progress — Last updated: [date]*
