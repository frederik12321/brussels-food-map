# Brussels Restaurant Authenticity Validation Report

## Executive Summary

**Total Validated:** 114 restaurants
- **Diaspora Group (with bonus):** 85 restaurants validated
- **Control Group (no bonus):** 29 restaurants validated

## Key Insight: Inhoud Boven Naam

**De belangrijkste les uit deze validatie: authenticiteit zit in de INHOUD, niet in de naam.**

Een restaurant met een generieke naam kan uitstekende authentieke keuken serveren, terwijl een restaurant met een "exotische" naam troep kan zijn. De beste indicatoren voor authenticiteit zijn:
1. **Hoe lang bestaat het restaurant?** (5+ jaar = bewezen kwaliteit)
2. **Rating en aantal reviews** (4.3+ met 200+ reviews)
3. **Prijsniveau** (budget = vaak authentieker)
4. **Locatie** (buurtrestaurant vs toeristengebied)
5. **Foto's van het eten** (ziet het er echt uit?)

## Diaspora Bonus Accuracy

### Diaspora Group Results (85 restaurants)
| Verdict | Count | Percentage |
|---------|-------|------------|
| CORRECT | 68 | 80.0% |
| FOUT | 9 | 10.6% |
| TWIJFEL | 8 | 9.4% |

**Accuracy Rate: 80.0%** (restaurants correctly receiving diaspora bonus)

### Control Group Results (29 restaurants)
| Verdict | Count | Notes |
|---------|-------|-------|
| N/A | 12 | Correctly no bonus |
| FOUT | 8 | SHOULD have bonus (false negatives) |
| TWIJFEL | 6 | Borderline cases |
| CORRECT | 3 | Authentic without bonus marker |

**False Negative Rate: 27.6%** (control group restaurants that SHOULD have diaspora bonus)

## Key Findings

### 1. Authenticity Works Well For:
- **Turkish restaurants** in Turkish neighborhoods (Schaerbeek, Saint-Josse) with 5+ years history
- **Lebanese restaurants** with budget prices and high review counts
- **Indian restaurants** with regional specializations (Hyderabadi, Punjabi)
- **African restaurants** in Matongé with traditional dishes (yassa, thieboudienne)

### 2. Incorrectly Assigned Diaspora Bonus (FOUT):
1. **Shanghai** - Rue des Bouchers (tourist trap), 3.8 rating
2. **Taste of Taj Mahal** - 3.1 rating, quality issues
3. **Restaurant Umā** - Modern European fine dining, not diaspora
4. **VIAGE Grill** - Casino restaurant
5. **Chicago burger** - 1.3 rating, poor quality
6. **Mare** - Wolf food market stall
7. **Bistro** - Station snackbar (1 review)
8. **Reboost açai** - Modern health food concept, not authentic Brazilian

### 3. Missing Diaspora Bonus (False Negatives in Control):
1. **Levent Börek Künefe** - Turkish bakery with Turkish diacritics
2. **Mithu da Dhaba** - Authentic Punjabi dhaba concept
3. **Somuncu Baba Boulangerie** - Turkish bakery
4. **Coimbra** - Portuguese city name in Portuguese neighborhood
5. **Casa del Sud** - Italian restaurant with Italian name
6. **Hibiscus** - West African cuisine (yassa) without African markers
7. **Atelier Acqua e Sale** - Authentic Italian name

### 4. Fusie vs Pure Diaspora:
Let op het verschil:
- **Penafidélis Bar** - Portugees-Belgische fusie (geen pure diaspora)
- **ANJALI** - Modern Indian (upscale, niet traditioneel)
- **Greekit** - Modern Greek concept (naam = woordspeling)
- **Inanna Resto Bar** - Mesopotamische naam maar moderne bar

## Years Open Distribution

| Duration | Count | Percentage | Avg Auth Score |
|----------|-------|------------|----------------|
| <2 years | 18 | 15.8% | 6.2 |
| 2-5 years | 58 | 50.9% | 7.1 |
| 5-10 years | 32 | 28.1% | 7.5 |
| 10+ years | 6 | 5.3% | 7.8 |

**Insight:** Restaurants met 5+ jaar historie scoren gemiddeld hoger op authenticiteit. Longevity = kwaliteitsindicator.

## Cuisine Distribution (Top 12)

| Cuisine | Count | Avg Score | Best Example |
|---------|-------|-----------|--------------|
| Turkish | 16 | 7.9 | YÖRÜK ÇADIRI (9) |
| Lebanese | 12 | 7.5 | Snack TASNEEM (9) |
| Indian | 10 | 7.1 | Rangla Punjab (8) |
| Chinese | 9 | 6.5 | Yi Chan (7) |
| Greek | 9 | 7.4 | Pellas (8) |
| African | 6 | 7.8 | Thieyp (9) |
| Vietnamese | 6 | 7.5 | Phở & Bánh Mì (8) |
| Brazilian | 4 | 7.3 | Brazil Grill (8) |
| Portuguese | 3 | 7.0 | Coimbra (8) |
| Italian | 5 | 6.4 | Casa del Sud (7) |
| Seafood (Belgian) | 5 | 5.4 | Noordzee (6) |
| Fast Food/Halal | 4 | 6.8 | Snack Le Botanique (7) |

## Patterns That Predict Quality/Authenticity

### Strong Positive Indicators:
1. **Longevity** (5+ years open) - strongest predictor
2. **High review count** (500+) with 4.3+ rating
3. **Budget prices** (€1-10 or €10-20)
4. **Location in ethnic neighborhoods** (Saint-Josse, Matongé, Saint-Gilles Portuguese area)
5. **Late night opening** (indicates local clientele)
6. **Native language reviews** (Turkish, Arabic, Portuguese)

### Red Flags:
1. **Rue des Bouchers location** - Tourist trap street
2. **Wolf Food Market / Food halls** - Not restaurants
3. **Casino/hotel restaurants** - Generic dining
4. **Rating below 3.5** - Quality issues
5. **Very few reviews** (<20) - Unproven
6. **"Kitchen" or modern buzzwords in name** - Often fusion
7. **Temporarily closed** - Business problems

### Neutral (Context Dependent):
1. **Native language in name** - Helpful but not determinative
2. **Diacritics** - Good signal but many false negatives without
3. **Flag emojis** - Minor positive signal

## Recommendations for Algorithm Improvement

### 1. Add Longevity Bonus:
- 5-10 years: +0.02
- 10+ years: +0.03
- <1 year: -0.01

### 2. Add Review Quality Filter:
- Rating < 3.5: remove from consideration
- Reviews < 20: flag as unproven
- Reviews > 500 with 4.3+: +0.01

### 3. Improve Location-Based Scoring:
**Penalties:**
- Rue des Bouchers: -0.03
- Wolf Food Market: exclude
- Casino locations: -0.02

**Bonuses:**
- Saint-Josse: +0.01 for Turkish/Middle Eastern
- Matongé (Ixelles): +0.01 for African
- Saint-Gilles (Jean Volders area): +0.01 for Portuguese/Brazilian

### 4. Fix Cuisine Categories:
- "Bakery" should detect Turkish/ethnic bakeries
- "Other" category needs manual review
- "Asian" too generic - split by country
- "Fast Food" with "Halal" should be flagged as Middle Eastern

### 5. Content-Based Scoring:
Rather than relying on name patterns, consider:
- Google Maps category classification
- Review text analysis (mentions of specific dishes)
- Price level correlation with authenticity

## Conclusion

De diaspora bonus heeft een **80% accuracy rate** voor restaurants die hem krijgen, maar de **27.6% false negative rate** in de control group toont dat het algoritme authentieke restaurants mist.

**Belangrijkste verbeteringen:**
1. Focus op INHOUD (reviews, longevity, prijzen) niet alleen NAAM
2. Voeg longevity als belangrijke factor toe
3. Fix location-based penalties en bonuses
4. Verbeter cuisine categorisatie voor bakkerijen en "Other"

De beste authentieke restaurants hebben:
- 5+ jaar historie
- 4.3+ rating met 200+ reviews
- Budget tot mid-range prijzen
- Locatie in etnische wijken of buurten (niet toeristengebieden)

---
*Report generated: January 2026*
*Validated by: Google Maps data collection*
*Total restaurants validated: 114*
