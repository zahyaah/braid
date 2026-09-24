# Extraction quality report

Hand-annotated sample: 100 sentences. Annotated **before** the pipeline's output for these sentences was consulted: sentences were sampled (seed 20260923) and read cold, applying the five documented patterns (README.md) by eye. The only pipeline-adjacent information used was each passage's own title (needed to annotate pronoun-subject sentences correctly, since entities.py substitutes third-person pronouns with the title) -- that is corpus metadata, not extraction output.

## Precision and recall

| Metric | Value | 95% Wilson CI | Correct | Total |
|---|---|---|---|---|
| Precision | 0.577 | [0.489, 0.661] | 71 | 123 |
| Recall | 0.899 | [0.813, 0.948] | 71 | 79 |

## Full-corpus extraction: 4954 triples

| Relation | Count |
|---|---|
| be | 1918 |
| include | 125 |
| have | 89 |
| star | 79 |
| write | 65 |
| feature | 61 |
| play | 60 |
| air on | 53 |
| win | 48 |
| release | 38 |
| receive | 36 |
| appear in | 35 |
| produce | 34 |
| provide | 34 |
| reach | 30 |
| serve as | 30 |
| consist of | 27 |
| contain | 26 |
| make | 26 |
| use | 26 |
| represent | 23 |
| air in | 22 |
| follow | 22 |
| take | 21 |
| create | 20 |
| host | 20 |
| found | 19 |
| star in | 19 |
| publish | 18 |
| comprise | 16 |
| play in | 16 |
| replace | 16 |
| direct | 14 |
| earn | 14 |
| lead | 14 |
| voice | 14 |
| appear on | 13 |
| become in | 13 |
| compete in | 13 |
| study | 13 |
| come from | 12 |
| cover | 12 |
| defeat | 12 |
| establish | 12 |
| go to | 12 |
| join | 12 |
| serve | 12 |
| sign | 12 |
| give | 11 |
| move to | 11 |
| operate | 11 |
| star as | 11 |
| die in | 10 |
| leave | 10 |
| play for | 10 |
| throw | 10 |
| attend | 9 |
| change | 9 |
| finish | 9 |
| mark | 9 |
| see | 9 |
| spend | 9 |
| tell | 9 |
| announce | 8 |
| appear as | 8 |
| bring | 8 |
| complete | 8 |
| focus on | 8 |
| open | 8 |
| perform | 8 |
| record | 8 |
| refer to | 8 |
| screen at | 8 |
| start | 8 |
| become with | 7 |
| begin | 7 |
| coach | 7 |
| do | 7 |
| examine | 7 |
| garner | 7 |
| house | 7 |
| link | 7 |
| list | 7 |
| lose | 7 |
| remain in | 7 |
| sell | 7 |
| support | 7 |
| achieve | 6 |
| call | 6 |
| carry | 6 |
| debut in | 6 |
| find | 6 |
| form | 6 |
| fuse | 6 |
| participate in | 6 |
| pitch | 6 |
| premier at | 6 |
| premier on | 6 |
| run from | 6 |
| serve at | 6 |
| work for | 6 |
| become after | 5 |
| begin in | 5 |
| build | 5 |
| choose | 5 |
| compose | 5 |
| consider | 5 |
| debut at | 5 |
| define | 5 |
| describe | 5 |
| design | 5 |
| determine | 5 |
| develop | 5 |
| display | 5 |
| dominate | 5 |
| draw | 5 |
| encompass | 5 |
| hold | 5 |
| inspire | 5 |
| mean | 5 |
| name | 5 |
| obtain | 5 |
| occupy | 5 |
| open in | 5 |
| portray | 5 |
| remain until | 5 |
| result in | 5 |
| rise to | 5 |
| run on | 5 |
| run through | 5 |
| screen in | 5 |
| start in | 5 |
| strike | 5 |
| want | 5 |
| work as | 5 |
| work on | 5 |
| accomplish | 4 |
| administer | 4 |
| air from | 4 |
| allow | 4 |
| begin after | 4 |
| begin on | 4 |
| cancel | 4 |
| certify | 4 |
| come to | 4 |
| continue through | 4 |
| contribute to | 4 |
| deliver | 4 |
| discover | 4 |
| extend to | 4 |
| gain | 4 |
| grow in | 4 |
| lead to | 4 |
| limit | 4 |
| live in | 4 |
| market | 4 |
| move in | 4 |
| open as | 4 |
| open on | 4 |
| own | 4 |
| peak at | 4 |
| peak on | 4 |
| premier in | 4 |
| present | 4 |
| put | 4 |
| range from | 4 |
| recognize | 4 |
| reprise | 4 |
| revolve around | 4 |
| run for | 4 |
| serve from | 4 |
| serve in | 4 |
| set | 4 |
| settle | 4 |
| sign with | 4 |
| spawn | 4 |
| stand on | 4 |
| star on | 4 |
| visit | 4 |
| win against | 4 |
| adapt | 3 |
| advocate for | 3 |
| apply in | 3 |
| arrive in | 3 |
| ask | 3 |
| attack | 3 |
| begin with | 3 |
| chart | 3 |
| collaborate on | 3 |
| come after | 3 |
| come in | 3 |
| come with | 3 |
| commission | 3 |
| debut as | 3 |
| declare | 3 |
| die at | 3 |
| die on | 3 |
| enlist | 3 |
| enter | 3 |
| experience | 3 |
| explore | 3 |
| extend along | 3 |
| face | 3 |
| fall below | 3 |
| fall since | 3 |
| file in | 3 |
| finance | 3 |
| finish in | 3 |
| finish with | 3 |
| graduate from | 3 |
| identify | 3 |
| influence | 3 |
| introduce | 3 |
| issue | 3 |
| judge | 3 |
| leverage | 3 |
| love | 3 |
| manufacture | 3 |
| meet | 3 |
| narrate | 3 |
| occur in | 3 |
| offer | 3 |
| operate between | 3 |
| operate on | 3 |
| organise | 3 |
| partner | 3 |
| pen | 3 |
| place | 3 |
| play at | 3 |
| promote | 3 |
| reference | 3 |
| reflect | 3 |
| relate to | 3 |
| reside in | 3 |
| retire | 3 |
| rise in | 3 |
| rise with | 3 |
| run | 3 |
| run to | 3 |
| score | 3 |
| select | 3 |
| serve between | 3 |
| share | 3 |
| show | 3 |
| sing in | 3 |
| specialize in | 3 |
| stay for | 3 |
| supersede | 3 |
| teach | 3 |
| top | 3 |
| accompany | 2 |
| acquire | 2 |
| act as | 2 |
| act in | 2 |
| advance | 2 |
| air as | 2 |
| air at | 2 |
| appear between | 2 |
| appoint | 2 |
| arrive at | 2 |
| arrive on | 2 |
| assume | 2 |
| attempt in | 2 |
| attract | 2 |
| beat | 2 |
| become on | 2 |
| begin as | 2 |
| begin following | 2 |
| belong to | 2 |
| capture | 2 |
| cast | 2 |
| chart at | 2 |
| choose between | 2 |
| chronicle | 2 |
| cite | 2 |
| collect | 2 |
| combine | 2 |
| come alongside | 2 |
| commence on | 2 |
| continue as | 2 |
| control | 2 |
| cost | 2 |
| debut by | 2 |
| debut on | 2 |
| dedicate | 2 |
| depict | 2 |
| die along | 2 |
| die by | 2 |
| die due | 2 |
| draft | 2 |
| drop | 2 |
| echo | 2 |
| educate | 2 |
| elect | 2 |
| employ | 2 |
| end | 2 |
| end at | 2 |
| end in | 2 |
| ensure | 2 |
| expand | 2 |
| explain | 2 |
| export | 2 |
| fare on | 2 |
| favor | 2 |
| feature in | 2 |
| flow through | 2 |
| generate | 2 |
| get | 2 |
| go into | 2 |
| got | 2 |
| govern | 2 |
| graduate in | 2 |
| gross | 2 |
| help | 2 |
| incorporate | 2 |
| intrigue | 2 |
| invest in | 2 |
| justify | 2 |
| lie at | 2 |
| lie on | 2 |
| lie with | 2 |
| manage | 2 |
| marry | 2 |
| master | 2 |
| meet with | 2 |
| merge | 2 |
| move from | 2 |
| need | 2 |
| open with | 2 |
| operate as | 2 |
| outline | 2 |
| overlook | 2 |
| owe | 2 |
| pass through | 2 |
| peak in | 2 |
| practise | 2 |
| praise | 2 |
| precede | 2 |
| prevent | 2 |
| prophesy | 2 |
| purchase | 2 |
| rap in | 2 |
| regard | 2 |
| rejoin | 2 |
| release on | 2 |
| remember | 2 |
| renew | 2 |
| resume after | 2 |
| retire in | 2 |
| return to | 2 |
| revel in | 2 |
| revive | 2 |
| send | 2 |
| serve during | 2 |
| serve under | 2 |
| ship | 2 |
| sign as | 2 |
| speak in | 2 |
| star alongside | 2 |
| start as | 2 |
| start with | 2 |
| stop in | 2 |
| succeed | 2 |
| target | 2 |
| teach at | 2 |
| trace | 2 |
| transfer to | 2 |
| trap for | 2 |
| travel | 2 |
| turn | 2 |
| watch | 2 |
| win in | 2 |
| work from | 2 |
| work in | 2 |
| work including | 2 |
| work with | 2 |
| work within | 2 |
| Stoppin | 1 |
| abandon | 1 |
| accommodate | 1 |
| act at | 1 |
| adopt | 1 |
| advance along | 1 |
| advance from | 1 |
| affect | 1 |
| affiliate in | 1 |
| affiliate with | 1 |
| agree after | 1 |
| air alongside | 1 |
| air during | 1 |
| allow in | 1 |
| amount to | 1 |
| amputate | 1 |
| appeal as | 1 |
| appeal to | 1 |
| appear over | 1 |
| appear since | 1 |
| apply | 1 |
| apply for | 1 |
| approach | 1 |
| approve | 1 |
| arise from | 1 |
| arrest | 1 |
| attempt during | 1 |
| authorize | 1 |
| award | 1 |
| bear | 1 |
| become as | 1 |
| become at | 1 |
| become for | 1 |
| belong | 1 |
| belong in | 1 |
| blend with | 1 |
| block | 1 |
| boast | 1 |
| borrow | 1 |
| break | 1 |
| break in | 1 |
| broadcast | 1 |
| broadcast on | 1 |
| buy | 1 |
| carve | 1 |
| catch with | 1 |
| cause | 1 |
| center on | 1 |
| chair | 1 |
| change between | 1 |
| chisel | 1 |
| choreograph | 1 |
| claim in | 1 |
| clash with | 1 |
| classify | 1 |
| close | 1 |
| close as | 1 |
| close at | 1 |
| close on | 1 |
| co | 1 |
| co alongside | 1 |
| co in | 1 |
| coach for | 1 |
| coach with | 1 |
| codify | 1 |
| coincide with | 1 |
| come across | 1 |
| come as | 1 |
| come during | 1 |
| come for | 1 |
| come on | 1 |
| command | 1 |
| commemorate | 1 |
| commence | 1 |
| commence in | 1 |
| comment to | 1 |
| compete alongside | 1 |
| compete since | 1 |
| compete with | 1 |
| compile | 1 |
| conceal | 1 |
| conceive | 1 |
| concentrate after | 1 |
| concentrate on | 1 |
| condemn | 1 |
| conduct from | 1 |
| connect | 1 |
| constitute | 1 |
| continue at | 1 |
| continue because | 1 |
| continue in | 1 |
| continue to | 1 |
| continue until | 1 |
| contract | 1 |
| contribute | 1 |
| create for | 1 |
| credit | 1 |
| cut to | 1 |
| dance in | 1 |
| date | 1 |
| date to | 1 |
| dawn from | 1 |
| debut after | 1 |
| debut for | 1 |
| decide | 1 |
| decree | 1 |
| defend | 1 |
| describe in | 1 |
| designate | 1 |
| desire | 1 |
| destroy | 1 |
| develop from | 1 |
| develop in | 1 |
| develop to | 1 |
| deviate from | 1 |
| devote | 1 |
| die from | 1 |
| dig | 1 |
| disappear in | 1 |
| disband in | 1 |
| discard | 1 |
| discover in | 1 |
| discuss | 1 |
| dissolve in | 1 |
| distribute | 1 |
| diverge from | 1 |
| diverge than | 1 |
| divide | 1 |
| draw on | 1 |
| draw with | 1 |
| drive | 1 |
| drum with | 1 |
| embark on | 1 |
| embed in | 1 |
| enable | 1 |
| encourage | 1 |
| end on | 1 |
| endure | 1 |
| enlarge in | 1 |
| enlarge upon | 1 |
| enter after | 1 |
| enter into | 1 |
| erect | 1 |
| erect in | 1 |
| erode | 1 |
| eschew | 1 |
| evolve because | 1 |
| excavate | 1 |
| exclude | 1 |
| exhibit in | 1 |
| expand from | 1 |
| expand on | 1 |
| expand to | 1 |
| explore as | 1 |
| explore in | 1 |
| extend by | 1 |
| fall for | 1 |
| fall from | 1 |
| fall in | 1 |
| fall into | 1 |
| fall to | 1 |
| fall under | 1 |
| fear | 1 |
| feed into | 1 |
| file for | 1 |
| fill | 1 |
| film | 1 |
| find in | 1 |
| finish on | 1 |
| flank | 1 |
| flow into | 1 |
| fly from | 1 |
| focus unlike | 1 |
| form in | 1 |
| foster | 1 |
| free | 1 |
| function as | 1 |
| fund | 1 |
| gather in | 1 |
| go as | 1 |
| go at | 1 |
| go on | 1 |
| grab | 1 |
| graduate with | 1 |
| grow by | 1 |
| grow throughout | 1 |
| guard | 1 |
| have in | 1 |
| head from | 1 |
| hit on | 1 |
| hurt | 1 |
| ignore | 1 |
| illuminate | 1 |
| illustrate | 1 |
| impersonate | 1 |
| impress like | 1 |
| imprison | 1 |
| improve on | 1 |
| increase by | 1 |
| increase during | 1 |
| inhabit | 1 |
| instal | 1 |
| interchange on | 1 |
| interchange with | 1 |
| intersect | 1 |
| intersect with | 1 |
| invent | 1 |
| invent as | 1 |
| involve | 1 |
| join in | 1 |
| kidnap | 1 |
| kill | 1 |
| know | 1 |
| lack | 1 |
| land on | 1 |
| launch | 1 |
| launch as | 1 |
| launch in | 1 |
| launch on | 1 |
| lay | 1 |
| lease | 1 |
| leave at | 1 |
| leave before | 1 |
| lend | 1 |
| liberate | 1 |
| lie beyond | 1 |
| lie near | 1 |
| lie to | 1 |
| listen to | 1 |
| live at | 1 |
| look for | 1 |
| lose to | 1 |
| maintain | 1 |
| make after | 1 |
| make during | 1 |
| manage in | 1 |
| merge in | 1 |
| merge with | 1 |
| migrate to | 1 |
| migrate with | 1 |
| mirror | 1 |
| miss | 1 |
| model | 1 |
| modify | 1 |
| morph from | 1 |
| morph to | 1 |
| move after | 1 |
| move around | 1 |
| murder | 1 |
| nominate | 1 |
| note | 1 |
| number among | 1 |
| occur for | 1 |
| occur throughout | 1 |
| open to | 1 |
| operate at | 1 |
| operate during | 1 |
| operate from | 1 |
| operate without | 1 |
| oppose | 1 |
| oversee | 1 |
| paint | 1 |
| parallel | 1 |
| parody | 1 |
| participate | 1 |
| participate on | 1 |
| participate since | 1 |
| partner with | 1 |
| pay | 1 |
| peak with | 1 |
| perceive as | 1 |
| perform at | 1 |
| perform before | 1 |
| perform for | 1 |
| perform in | 1 |
| perform on | 1 |
| perform with | 1 |
| persuade | 1 |
| petition | 1 |
| pick | 1 |
| play besides | 1 |
| play during | 1 |
| play opposite | 1 |
| plead in | 1 |
| post | 1 |
| practice | 1 |
| predict | 1 |
| premier with | 1 |
| premiere in | 1 |
| prepare | 1 |
| preview | 1 |
| pride | 1 |
| print | 1 |
| produce despite | 1 |
| produce in | 1 |
| protest | 1 |
| pull | 1 |
| pursue | 1 |
| race on | 1 |
| rank | 1 |
| rank for | 1 |
| rank in | 1 |
| rap about | 1 |
| re in | 1 |
| read | 1 |
| receive from | 1 |
| recruit | 1 |
| refer in | 1 |
| reject | 1 |
| release into | 1 |
| remain after | 1 |
| remain as | 1 |
| remain at | 1 |
| remain atop | 1 |
| remain due | 1 |
| remain for | 1 |
| remain with | 1 |
| remarry in | 1 |
| remarry to | 1 |
| rename | 1 |
| reorganize | 1 |
| report | 1 |
| repudiate | 1 |
| require | 1 |
| rerelease | 1 |
| resolve | 1 |
| respond with | 1 |
| rest upon | 1 |
| restrict | 1 |
| result from | 1 |
| retain | 1 |
| retire after | 1 |
| retire from | 1 |
| return as | 1 |
| return in | 1 |
| reunite on | 1 |
| reunite with | 1 |
| reveal | 1 |
| revolve with | 1 |
| rise as | 1 |
| rise behind | 1 |
| rise by | 1 |
| rise following | 1 |
| rule with | 1 |
| run along | 1 |
| run as | 1 |
| run including | 1 |
| run with | 1 |
| run within | 1 |
| say | 1 |
| say in | 1 |
| scratch | 1 |
| secede from | 1 |
| secede in | 1 |
| seem in | 1 |
| seep into | 1 |
| sell around | 1 |
| sell for | 1 |
| sell under | 1 |
| sentence | 1 |
| serve after | 1 |
| serve davis)—from | 1 |
| serve for | 1 |
| serve on | 1 |
| serve over | 1 |
| serve to | 1 |
| serve with | 1 |
| service | 1 |
| set following | 1 |
| settle in | 1 |
| settle on | 1 |
| shift by | 1 |
| shift to | 1 |
| shorten | 1 |
| sign in | 1 |
| sign on | 1 |
| sign to | 1 |
| sing | 1 |
| sit after | 1 |
| sit as | 1 |
| sit at | 1 |
| sit atop | 1 |
| sit in | 1 |
| sleep beside | 1 |
| smooth over | 1 |
| snap | 1 |
| span | 1 |
| sparkle like | 1 |
| speak about | 1 |
| speak to | 1 |
| spread from | 1 |
| spread to | 1 |
| stand as | 1 |
| star with | 1 |
| start at | 1 |
| start for | 1 |
| start from | 1 |
| start on | 1 |
| stay at | 1 |
| stay in | 1 |
| stay on | 1 |
| steer | 1 |
| stop | 1 |
| stretch | 1 |
| stretch from | 1 |
| study under | 1 |
| submit | 1 |
| succeed for | 1 |
| succeed in | 1 |
| supervise | 1 |
| surpass | 1 |
| survey | 1 |
| switch to | 1 |
| talk of | 1 |
| talk unlike | 1 |
| task | 1 |
| teach during | 1 |
| teach from | 1 |
| teach since | 1 |
| team with | 1 |
| term | 1 |
| terminate on | 1 |
| test | 1 |
| thank | 1 |
| thump | 1 |
| tie | 1 |
| tour | 1 |
| tour as | 1 |
| tour from | 1 |
| tour throughout | 1 |
| train in | 1 |
| train with | 1 |
| transition at | 1 |
| transition from | 1 |
| transition to | 1 |
| transmit | 1 |
| transport to | 1 |
| trap in | 1 |
| treat | 1 |
| try | 1 |
| try in | 1 |
| turn into | 1 |
| type with | 1 |
| unfold through | 1 |
| utilize | 1 |
| violate | 1 |
| vote | 1 |
| walk into | 1 |
| witness | 1 |
| work under | 1 |
| work until | 1 |
| write for | 1 |
| yield | 1 |

## Annotation methodology and its limitations

Gold triples were written using the same five patterns the pipeline
implements (active SVO, passive+agent, copular, prep-object, conjunction
expansion), applied by manual reading rather than by predicting spaCy's exact
parse tree. Subject/object text uses the core entity only (e.g. "Mike
Nichols", not "director Mike Nichols"); `compare()` uses containment matching
specifically so an annotator's minimal span still counts as correct against
the pipeline's fuller syntactic span (see quality.py's docstring).

**Annotation was conservative, not exhaustive**, for sentences with multiple
plausible triples (conjoined attributes, multiple clauses): one representative
triple was recorded rather than every one. Spot-checking the unmatched
extracted triples after the real run confirmed this directly -- a substantial
share of triples counted as "extra" (lowering precision) are additional
correct facts the gold set simply never recorded, not extraction errors:
`(four-piece band, consist of, Tim Commerford)`, `(students, obtain, master's
degrees)`, `(Rudolph Wendelin, be, best-known artist behind Smokey Bear)` --
all correct, all conjuncts or clauses this annotation pass chose not to
duplicate. **The measured precision above is therefore a conservative lower
bound**, not a point estimate to be taken at face value; the true precision on
a fully exhaustive gold standard is very likely higher.

**Two real bugs were found and fixed** during this process, before the
numbers above were finalized (both with regression tests in
`tests/extract/test_patterns.py`):

1. **Relative pronoun subjects** ("which", "who", "that" as a relative
   pronoun -- POS tag WDT/WP) were treated as ordinary subjects, since only
   third-person personal pronouns are substituted (entities.py). This
   produced nonsensical triples like `(which, air on, ABC)` from "the movie,
   which aired on ABC...". Fixed by skipping WH-tagged subjects entirely
   (no triple emitted, consistent with the module's existing
   "err toward silence" rule for interrogative sentences) rather than
   attempting antecedent resolution, which is out of scope for the documented
   pronoun-substitution rule (title-only, not general coreference).
2. **Relation casing**: a sentence-initial fronted preposition ("With her
   approach, Kamen became...") left its surface capitalization in the
   relation string (`"become With"` instead of `"become with"`).

**Known, documented gaps** (not fixed, out of the documented pattern set's
scope -- see README.md's "What is not extracted"):
- Copula verbs other than literal "be" ("become", "remain", "seem") are not
  covered by pattern 3.
- Adjectival predicates (`acomp`: "is correct") are not covered by pattern 3,
  which only matches noun-phrase predicates (`attr`).
- Clausal complements (`ccomp`: "notes that X") are not covered by pattern 1,
  which requires a nominal `dobj`.
- **Conjoined verb phrases are not expanded.** "Allen was born in Los
  Angeles and currently lives in Lancaster" only ever considers the verb a
  subject's `head` directly governs; a second conjoined verb sharing the same
  subject is not visited. Pattern 5 (conjunction expansion) only covers
  conjoined *subjects and objects*, not conjoined *verbs* -- a real,
  identified limitation, not yet fixed given scope/time.
- **Parallel/positional conjunctions produce a cartesian product, not
  paired triples.** "X, Y, Z were replaced by A, B, C respectively" would
  expand to nine triples (every subject conjunct paired with every object
  conjunct) instead of the three correctly-paired ones. Not fixed; flagged
  here because it was observed directly in the sample (passage
  `de3fe845a68ba037`) and not annotated in gold for that reason.

