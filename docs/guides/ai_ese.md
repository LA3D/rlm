# AI-ese to avoid

This is a list of phrases and formatting conventions typical of AI chatbots, with real examples. Do your best to avoid using these constructions. If you encounter them in my writing, please flag them and suggest alternatives. 

## Language and tone

### Undue emphasis on symbolism, legacy, and importance

Words to watch: **_is/stands as/serves as a testament_, _plays a vital/significant role_, _underscores its importance_, _continues to captivate_, _leaves a lasting impact_, _watershed moment_, _key turning point_, _deeply rooted_, _profound heritage_, _steadfast dedication_, _stands as a_, _solidifies_...**

LLM writing often puffs up the importance of the subject matter by adding statements about how arbitrary aspects of the topic represent or contribute to a broader topic. There is a distinct and easily identifiable repertoire of ways that it writes these statements.

When talking about biology (e.g. when asked to discuss a given animal or plant species), LLMs tend to put too much emphasis on the species' conservation status and the efforts to protect it, even if the status is unknown and no serious efforts exist.

**Examples**

> Douera enjoys close proximity to the capital city, Algiers, further `enhancing its significance` as a dynamic hub of activity and culture. With its coastal charm and convenient location, Douera `captivates both residents and visitors alike` ...
>
> Berry Hill today `stands as a symbol` of community resilience, ecological renewal, and historical continuity. Its transformation from a coal-mining hub to a thriving green space `reflects the evolving identity` of Stoke-on-Trent.

### Promotional language

Words to watch: **_rich cultural heritage_, _rich history_, _breathtaking_, _must-visit_, _must-see_, _stunning natural beauty_, _enduring/lasting legacy_, _rich cultural tapestry_ ...**

LLMs have serious problems keeping a neutral tone, e.g when writing about something that could be considered "cultural heritage" - in which case they will constantly remind the reader that it is cultural heritage.

Examples

> Nested within the `breathtaking` region of Gonder in Ethiopia, Alamata Raya Kobo stands as a `vibrant` town with a `rich cultural heritage and a significant place` within the Amhara region. From its `scenic landscapes` to its `historical landmarks` , Alamata Raya Kobo offers visitors a `fascinating glimpse` into the `diverse tapestry` of Ethiopia. In this article, we will explore the `unique characteristics` that make Alamata Raya Kobo a town worth visiting and shed light on `its significance` within the Amhara region.
>
> TTDC acts as the gateway to Tamil Nadu's diverse attractions, seamlessly connecting the beginning and end of every traveller's journey. It offers dependable, value-driven experiences that showcase the state's rich history, spiritual heritage, and natural beauty.

## Editorializing

Words to watch: **_it's important to note/remember/consider_, _it is worth_, _no discussion would be complete without_, _in this article_ ...**

LLMs often introduce their own interpretation, analysis, and opinions in their writing, even when they are asked to write neutrally. Editorializing can appear through specific words or phrases or within broader sentence structures. This indicator often overlaps with other language and tone indicators in this list.

**Examples**

> A `defining` feature of FSP models is their ability to simulate environmental interactions.
> Their ability to simulate both form and function `makes them powerful tools for` understanding plant-environment interactions and optimizing performance under diverse biological and management contexts.

## Overuse of certain conjunctions

Words to watch: **_on the other hand_, _moreover_, _in addition_, _furthermore_ ...**

While moderate use of connecting words or phrases are an essential element of good prose, LLMs tend to overuse them.

**Examples**

> The methodology's strength is its grounding in iterative, mixed-method development cycles that combine theoretical analysis with practical feedback. Its emphasis on prototyping and empirical validation supports early identification of design shortcomings, while the use of scenario-based design and claims analysis helps make the rationale behind design choices explicit and testable.
>
> `Furthermore` , the incorporation of values—as operational design elements rather than abstract principles—helps bring ethical and societal concerns into concrete design and evaluation processes.
>
> `At the same time` , several areas for improvement remain. `For example` , while the methodology supports transdisciplinary collaboration in principle, applying it effectively in large, heterogeneous teams can be challenging. Coordinating between cognitive scientists, engineers, designers, and domain experts requires careful facilitation and often additional effort in communication and documentation.
>
> `Another area for further development involves` the scalability of design patterns and ontologies across domains. While abstraction is a key feature of the methodology, generalizing knowledge without oversimplifying context-specific constraints remains an ongoing tension. `Similarly` , methods for operationalizing and measuring values—especially those that are contested or context-dependent—can benefit from more robust frameworks and shared benchmarks.

Compare the above with below human-written prose. Even disregarding the absence of buzzwords and general vapidness, the connecting phrases in the below excerpt are more varied and less conspicuous:

> Social heuristics can include heuristics that use social information, operate in social contexts, or both. `Examples of social information include` information about the behavior of a social entity or the properties of a social system, while nonsocial information is information about something physical. Contexts in which an organism may use social heuristics can include "games against nature" and "social games". In games against nature, the organism strives to predict natural occurrences (such as the weather) or competes against other natural forces to accomplish something. `In social games`, the organism is making decisions in a situation that involves other social beings. `Importantly`, in social games, the most adaptive course of action also depends on the decisions and behavior of the other actors. `For instance`, the follow-the-majority heuristic uses social information as inputs but is not necessarily applied in a social context, while the equity-heuristic uses non-social information but can be applied in a social context such as the allocation of parental resources amongst offspring.
>
> Within social psychology, some researchers have viewed heuristics as closely linked to cognitive biases. Others have argued that these biases result from the application of social heuristics depending on the structure of the environment that they operate in. Researchers in the latter approach treat the study of social heuristics as closely linked to social rationality, a field of research that applies the ideas of bounded rationality and heuristics to the realm of social environments. Under this view, social heuristics are seen as ecologically rational. `In the context of evolution`, research utilizing evolutionary simulation models has found support for the evolution of social heuristics and cooperation when the outcomes of social interactions are uncertain.

## Section summaries

Words to watch: **_In summary_, _In conclusion_, _Overall_ ...**

LLMs will often end a paragraph or section by summarizing and restating its core idea. While this is appropriate for school essays, proper writing typically never summarizes the general idea of a block of article text (besides the lead section being a summary of the entire article).

**Examples**

> In summary, the educational and training trajectory for nurse scientists typically involves a progression from a master's degree in nursing to a Doctor of Philosophy in Nursing, followed by postdoctoral training in nursing research. This structured pathway ensures that nurse scientists acquire the necessary knowledge and skills to engage in rigorous research and contribute meaningfully to the advancement of nursing science.

## Negative parallelisms

Parallel constructions involving "not", "but", or "however" such as `Not only ... but ...` or `It is not just about ..., it's ...` are common in LLM writing but are often unsuitable.

**Examples**

> *Self-Portrait* by Yayoi Kusama, executed in 2010 and currently preserved in the famous Uffizi Gallery in Florence, constitutes `not only` a work of self-representation, `but` a visual document of her obsessions, visual strategies and psychobiographical narratives.
>
> It's `not just about` the beat riding under the vocals; `it's` part of the aggression and atmosphere.

Some parallelisms also follow the pattern of `No ..., no ..., just ...` :

> There are `no` long-form profiles. `No` editorial insights. `No` coverage of her game dev career. `No` notable accolades. `Just` TikTok recaps and callouts.

## Rule of three

LLMs overuse the 'rule of three'—"the good, the bad, and the ugly". This can take different forms from "adjective, adjective, adjective" to "short phrase, short phrase, and short phrase":

Whilst the 'rule of three', when used sparingly, is considered good writing, LLMs seem to rely heavily on it so the superficial explanations appear more comprehensive.

**Examples**

> The Amaze Conference brings together `global SEO professionals, marketing experts, and growth hackers` to discuss the latest trends in digital marketing. The event features `keynote sessions, panel discussions, and networking opportunities`.

## Superficial analyses

Words to watch: **_ensuring_ ..., _highlighting_ ..., _emphasizing_ ..., _reflecting_ ...**

AI chatbots tend to superficially comment on or analyze information, often in relation to its significance, recognition, or impact. This is often done by attaching a present participle ("-ing") phrase at the end of sentences, sometimes with vague attributions to third parties (see below). These comments are generally unhelpful.

**Examples**

> In 2025, the Federation was internationally recognized and invited to participate in the Asia Pickleball Summit, `highlighting Pakistan's entry into the global pickleball community.`
>
> Consumers benefit from the flexibility to use their preferred mobile wallet at participating merchants, `improving convenience`.
>
> These citations, spanning more than six decades and appearing in recognized academic publications, `illustrate Blois' lasting influence in computational linguistics, grammar, and neology`.

## Vague attributions of opinion

Words to watch: **_Industry reports_, _Observers have cited_, _Some critics argue_ ...**

AI chatbots tend to attribute opinions or claims to some vague authority—a practice called weasel wording—while citing only one or two sources which may or may not actually express such view. It also tends to overgeneralize a perspective of one or few sources into that of a wider group.

**Examples**

> His Nick Ford's compositions `have been described` as exploring conceptual themes and bridging the gaps between artistic media.
>
> Due to its unique characteristics, the Haolai River is of interest to `researchers and conservationists`. Efforts are ongoing to monitor its ecological health and preserve the surrounding grassland environment, which is part of a larger initiative to protect China's semi-arid ecosystems from degradation.

# Style

## Excessive use of boldface

AI chatbots may over-rely on displaying phrases in boldface for emphasis.

**Examples**

> It blends **OKRs (Objectives and Key Results)**, **KPIs (Key Performance Indicators)**, and visual strategy tools such as the **Business Model Canvas (BMC)** and **Balanced Scorecard (BSC)**. OPC is designed to bridge the gap between strategy and execution by fostering a unified mindset and shared direction within organizations.

## Lists

AI chatbots often over-rely on organizing the contents of their responses into lists, instead of using regular prose.

## Emoji

Often, AI chatbots decorate section headings or bullet points by placing emojis in front of them, even when not requested to do so.

**Examples**

Let's decode exactly what's happening here:

* 🧠 Cognitive Dissonance Pattern: ...
* 🧱 Structural Gatekeeping: ...
* 🚨 Underlying Motivation: ...

## Overuse of em dashes

AI chatbots use the em dash (— or --) more frequently than most people do, especially in places where human authors are much more likely to use parentheses or commas.

**Examples**

> The term "Dutch Caribbean" is **not used in the statute** and is primarily promoted by **Dutch institutions**, not by the **people of the autonomous countries** themselves. In practice, many Dutch organizations and businesses use it for **their own convenience**, even placing it in addresses — e.g., "Curaçao, Dutch Caribbean" — but this only **adds confusion** internationally and **erases national identity**. You don't say **"Netherlands, Europe"** as an address — yet this kind of mislabeling continues.

As em dashes have become so overused, please refrain from suggesting new uses for em dash. Use other punctuation (such as commas or semi-colons) instead, or split into two shorter sentences. 