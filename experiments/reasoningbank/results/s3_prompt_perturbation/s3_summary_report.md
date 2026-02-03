# Experiment S3: Prompt Perturbation Effect - Summary Report

**Date**: 2026-02-03T15:56:27.615446

## Configuration

- Rollouts per task (k): 5
- Temperature: 0.7
- Explicit seeds: False
- Tasks: 5
- Strategies: none, prefix, thinking, rephrase

## Tasks

- `1_select_all_taxa_used_in_uniprot` [simple]
- `4_uniprot_mnemonic_id` [simple]
- `2_bacteria_taxa_and_their_scientific_name` [moderate]
- `121_proteins_and_diseases_linked` [moderate]
- `30_merged_loci` [moderate]

## Results by Strategy

### Performance Metrics

| Strategy | Pass@1 | Best-of-N | Trajectory Vendi | Efficiency | Mean Jaccard |
|----------|--------|-----------|------------------|------------|-------------|
| none     | 80.0% | 80.0% |   1.51 | 30.2% | 0.584 |
| prefix   | 80.0% | 80.0% |   1.68 | 33.5% | 0.598 |
| thinking | 80.0% | 80.0% |   1.65 | 32.9% | 0.593 |
| rephrase | 80.0% | 80.0% |   1.64 | 32.8% | 0.615 |

### Interpretation

**Best for trajectory diversity**: `prefix` (highest Trajectory Vendi Score)

**Best for sampling efficiency**: `prefix` (highest ratio of unique trajectories)

**Performance impact**:
- ✓ `prefix`: +0.0% vs baseline
- ✓ `thinking`: +0.0% vs baseline
- ✓ `rephrase`: +0.0% vs baseline

### Detailed Results by Task

#### 1_select_all_taxa_used_in_uniprot [simple]

*Select all taxa from the UniProt taxonomy*

| Strategy | Pass@1 | Best-of-N | Traj Vendi | Efficiency |
|----------|--------|-----------|------------|------------|
| none     | 100.0% | 100.0% |  1.62 | 32.4% |
| prefix   | 100.0% | 100.0% |  1.92 | 38.4% |
| thinking | 100.0% | 100.0% |  1.61 | 32.2% |
| rephrase | 100.0% | 100.0% |  1.74 | 34.8% |

#### 4_uniprot_mnemonic_id [simple]

*Select the UniProtKB entry with the mnemonic 'A4_HUMAN'*

| Strategy | Pass@1 | Best-of-N | Traj Vendi | Efficiency |
|----------|--------|-----------|------------|------------|
| none     | 100.0% | 100.0% |  1.88 | 37.7% |
| prefix   | 100.0% | 100.0% |  1.89 | 37.8% |
| thinking | 100.0% | 100.0% |  1.87 | 37.3% |
| rephrase | 100.0% | 100.0% |  1.67 | 33.5% |

#### 2_bacteria_taxa_and_their_scientific_name [moderate]

*Select all bacterial taxa and their scientific name from the UniProt taxonomy*

| Strategy | Pass@1 | Best-of-N | Traj Vendi | Efficiency |
|----------|--------|-----------|------------|------------|
| none     | 100.0% | 100.0% |  1.49 | 29.8% |
| prefix   | 100.0% | 100.0% |  2.05 | 41.0% |
| thinking | 100.0% | 100.0% |  1.74 | 34.8% |
| rephrase | 100.0% | 100.0% |  1.66 | 33.1% |

#### 121_proteins_and_diseases_linked [moderate]

*List all UniProtKB proteins and the diseases are annotated to be related.*

| Strategy | Pass@1 | Best-of-N | Traj Vendi | Efficiency |
|----------|--------|-----------|------------|------------|
| none     | 100.0% | 100.0% |  1.57 | 31.3% |
| prefix   | 100.0% | 100.0% |  1.52 | 30.4% |
| thinking | 100.0% | 100.0% |  2.02 | 40.4% |
| rephrase | 100.0% | 100.0% |  2.13 | 42.6% |

#### 30_merged_loci [moderate]

*Find UniProtKB entries with merged loci in Bordetella avium*

| Strategy | Pass@1 | Best-of-N | Traj Vendi | Efficiency |
|----------|--------|-----------|------------|------------|
| none     | 0.0% | 0.0% |  1.00 | 20.0% |
| prefix   | 0.0% | 0.0% |  1.00 | 20.0% |
| thinking | 0.0% | 0.0% |  1.00 | 20.0% |
| rephrase | 0.0% | 0.0% |  1.00 | 20.0% |

