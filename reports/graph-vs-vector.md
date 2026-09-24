# Criterion-3: Graph-sourced additions over dense retrieval

## Definition

A **graph-win** for a multi-hop evaluation query is a gold passage that (1) appears in the `fused` top-10 with **non-zero graph provenance**, and (2) is **absent from the `dense` top-10** (dense rank > 10 or not returned).

The count covers **every** multi-hop query in the queryset — no subset selection.

## Summary

| Metric | Value |
|---|---|
| Multi-hop queries (denominator) | 60 |
| Queries with ≥ 1 graph-win | 2 |
| Graph-win rate | 3.3% |

> [!CAUTION]
> Graph-win count is **2**, which is below the reporting threshold of 5. This is the finding: graph traversal contributes fewer unique gold passages over dense retrieval than expected for this queryset. See extraction-yield figures below.

## Per-query verdict table

| Query ID | Query text | Gold passage ID | Dense rank | Fused rank | Graph prov. | Verdict |
|---|---|---|---|---|---|---|
| mh-5a7149cf5542994082a3e773 | What 2015 British-Canadian-Irish romantic drama was Finola Dwyer a producer of? | 6e768e6cd85f9ed2 | 1 | 6 | 0.0000 | dense-wins |
| mh-5a7149cf5542994082a3e773 | What 2015 British-Canadian-Irish romantic drama was Finola Dwyer a producer of? | e76336800c245f52 | 2 | 2 | 0.0137 | neither |
| mh-5a714f6f5542994082a3e7b3 | How many people live in the County serviced by The Collier Area Transit system? | 1a7fb291862b6a48 | 1 | 8 | 0.0000 | dense-wins |
| mh-5a714f6f5542994082a3e7b3 | How many people live in the County serviced by The Collier Area Transit system? | 20f194388e574b3c | 2 | 10 | 0.0000 | dense-wins |
| mh-5a7320565542991f9a20c61d | who is younger Keith Bostic or Jerry Glanville ? | 872ce7bb7b882790 | 1 | 1 | 0.0159 | neither |
| mh-5a7320565542991f9a20c61d | who is younger Keith Bostic or Jerry Glanville ? | cfa64c6e3a5c59f1 | 3 | 2 | 0.0164 | neither |
| mh-5a733b835542991f9a20c6b2 | Which movie is loosley based off the Brother Grimm's "Iron Henry"? | b18f41a8e77780e0 | 1 | 2 | 0.0000 | dense-wins |
| mh-5a733b835542991f9a20c6b2 | Which movie is loosley based off the Brother Grimm's "Iron Henry"? | dd2a5277e29ae36b | 7 | — | 0.0000 | dense-wins |
| mh-5a7414d855429929fddd83db | What English professional football club, won the 1994 European Cup? Arsenal | 586cf7e25fbc66ba | 1 | 1 | 0.0154 | neither |
| mh-5a7414d855429929fddd83db | What English professional football club, won the 1994 European Cup? Arsenal | 9e88870ea9e57904 | 2 | 2 | 0.0152 | neither |
| mh-5a74f63e5542993748c89758 | A Troll in Central Park and All Dogs Go to Heaven were both directed by which person? | c181fcc44c66fa36 | 1 | 3 | 0.0145 | dense-wins |
| mh-5a74f63e5542993748c89758 | A Troll in Central Park and All Dogs Go to Heaven were both directed by which person? | cd578c521137d7ae | 2 | 5 | 0.0149 | dense-wins |
| mh-5a75e7b255429976ec32bc95 | Which games, Strange Synergy or Qwirkle, is a card game published by Steve Jackson Games? | a44440515b9a7d2a | 2 | 1 | 0.0154 | neither |
| mh-5a75e7b255429976ec32bc95 | Which games, Strange Synergy or Qwirkle, is a card game published by Steve Jackson Games? | da7fc5be9d0338e4 | 1 | 3 | 0.0105 | dense-wins |
| mh-5a76cb9b55429966f1a36bf2 | After David Stern retired from being commissioner of the NBA, this american lawyer and businessman succeed him and is now the current commissioner who is he? | 5ee6552866a8da60 | 2 | 2 | 0.0137 | neither |
| mh-5a76cb9b55429966f1a36bf2 | After David Stern retired from being commissioner of the NBA, this american lawyer and businessman succeed him and is now the current commissioner who is he? | 8c8d995931346bdc | 1 | 1 | 0.0156 | neither |
| mh-5a7736d85542994aec3b722b | Which film director is younger, Manoel de Oliveira or Alfonso Cuarón? | 85851fd419b391d0 | 2 | 6 | 0.0000 | dense-wins |
| mh-5a7736d85542994aec3b722b | Which film director is younger, Manoel de Oliveira or Alfonso Cuarón? | d918289da8006392 | 1 | 2 | 0.0114 | dense-wins |
| mh-5a77671255429966f1a36d21 | What aspect of the board game Diplomacy is not found in the board game Uncle Wiggily? | 8de2d06149bcc4c1 | 2 | 9 | 0.0000 | dense-wins |
| mh-5a77671255429966f1a36d21 | What aspect of the board game Diplomacy is not found in the board game Uncle Wiggily? | d023c335b3d75570 | 1 | 2 | 0.0125 | dense-wins |
| mh-5a778a3b5542992a6e59dec7 | What 1991 Disney film is also a 1946 French romantic fantasy film directed by French poet and filmmaker Jean Cocteau? | 856eaf3e04f88db8 | 1 | 2 | 0.0125 | dense-wins |
| mh-5a778a3b5542992a6e59dec7 | What 1991 Disney film is also a 1946 French romantic fantasy film directed by French poet and filmmaker Jean Cocteau? | e0f221419935b1c2 | 2 | 1 | 0.0145 | neither |
| mh-5a778e8755429949eeb29ef4 | St Anne's Academy is an 11–18 mixed comprehensive academy is located in a town that had how many inhabitants in 2011 ? | a7f37a5d2bfd3df9 | 4 | — | 0.0000 | dense-wins |
| mh-5a778e8755429949eeb29ef4 | St Anne's Academy is an 11–18 mixed comprehensive academy is located in a town that had how many inhabitants in 2011 ? | e5c38b8625407c95 | 1 | 1 | 0.0116 | neither |
| mh-5a78ce79554299029c4b5ea1 | Jacques Coghen is a direct ancestor to the spouse of which Belgian Queen? | 8409c91c65b1d4c1 | 1 | 2 | 0.0000 | dense-wins |
| mh-5a78ce79554299029c4b5ea1 | Jacques Coghen is a direct ancestor to the spouse of which Belgian Queen? | aeeb4b25079395a2 | 2 | 4 | 0.0000 | dense-wins |
| mh-5a79178d554299029c4b5ef9 | Which member of the music group Guy spearheaded the fusion genre New Jack Swing with Bernard Belle in the 1980's? | a065fa7ca8404521 | 4 | 2 | 0.0154 | neither |
| mh-5a79178d554299029c4b5ef9 | Which member of the music group Guy spearheaded the fusion genre New Jack Swing with Bernard Belle in the 1980's? | b34f78e786e64a22 | 1 | 1 | 0.0156 | neither |
| mh-5a79f27e5542990198eaf014 | Who was born first Dame Zara Kate Bate or Harold Edward Holt? | 4ef3563d0c454ee7 | 1 | 2 | 0.0154 | dense-wins |
| mh-5a79f27e5542990198eaf014 | Who was born first Dame Zara Kate Bate or Harold Edward Holt? | b582b90d5c0abaaa | 2 | 1 | 0.0161 | neither |
| mh-5a7a3d435542996a35c17154 | The Swallow Bluff Island Mounds is a Mississippian culture archaeological site that is located in this river which was once known by what name? | dc3386e137676b8c | 1 | 6 | 0.0000 | dense-wins |
| mh-5a7a3d435542996a35c17154 | The Swallow Bluff Island Mounds is a Mississippian culture archaeological site that is located in this river which was once known by what name? | e6b5dab32f35f4c7 | — | — | 0.0000 | neither |
| mh-5a7a60f15542990783324f35 | Sam Quartin starred in which movie, alongside a controversial singer whose stage name combines the names of Marilyn Monroe and Charles Manson? | 35efbddbb8c13efc | 1 | 1 | 0.0164 | neither |
| mh-5a7a60f15542990783324f35 | Sam Quartin starred in which movie, alongside a controversial singer whose stage name combines the names of Marilyn Monroe and Charles Manson? | 7cc0296ded8f3c74 | 2 | 2 | 0.0112 | neither |
| mh-5a7b74485542997c3ec97190 | 100 indviduals with the surname 'Preradovic' died at which concentration camp that straddled the southern border of the Hasburg Monarchy? | 2ac8df6de3b72c11 | 1 | 5 | 0.0000 | dense-wins |
| mh-5a7b74485542997c3ec97190 | 100 indviduals with the surname 'Preradovic' died at which concentration camp that straddled the southern border of the Hasburg Monarchy? | 917e36e418007f3d | 5 | 9 | 0.0000 | dense-wins |
| mh-5a7c221f554299683c1c62d2 | New Hampshire Route 124 runs between two regions, one of which is found in Cheshire County, New Hampshire, United States with the population of about 2000 and is named what? | 9f0a3c8e6d79939d | 1 | 1 | 0.0103 | neither |
| mh-5a7c221f554299683c1c62d2 | New Hampshire Route 124 runs between two regions, one of which is found in Cheshire County, New Hampshire, United States with the population of about 2000 and is named what? | de7801efcd3e380c | 3 | 3 | 0.0093 | neither |
| mh-5a7ce0bc55429909bec76863 | Which show which aired on NBC from September 22, 1994, to May 6, 2004, has the fifteenth episode entitled, "The One with the Girl Who Hits Joey"? | 47399c701acf21c1 | 2 | 7 | 0.0102 | dense-wins |
| mh-5a7ce0bc55429909bec76863 | Which show which aired on NBC from September 22, 1994, to May 6, 2004, has the fifteenth episode entitled, "The One with the Girl Who Hits Joey"? | 953a9c81da09973d | 1 | 1 | 0.0159 | neither |
| mh-5a7d2aa05542995f4f40221f | What mixed martial arts even took place at a closed hotel and casino on the Boardwalk in Atlantic City, owned by Trump Entertainment Resorts? | 6893fde555c951fc | 1 | 2 | 0.0135 | dense-wins |
| mh-5a7d2aa05542995f4f40221f | What mixed martial arts even took place at a closed hotel and casino on the Boardwalk in Atlantic City, owned by Trump Entertainment Resorts? | dbebf2509b3c8dfe | 10 | — | 0.0000 | dense-wins |
| mh-5a7d2afd5542995f4f402221 | Who is older, Ferdi Taygan or Mahesh Bhupathi? | 14175bf62056eb75 | 2 | 3 | 0.0149 | dense-wins |
| mh-5a7d2afd5542995f4f402221 | Who is older, Ferdi Taygan or Mahesh Bhupathi? | 555c572921b5ae94 | 1 | 10 | 0.0000 | dense-wins |
| mh-5a7d32af55429907fabef0ca | Straight to Hell was the first ever country music release to merit this what organization's Parental Advisory label? | 26934d45e71da4b6 | 2 | 9 | 0.0000 | dense-wins |
| mh-5a7d32af55429907fabef0ca | Straight to Hell was the first ever country music release to merit this what organization's Parental Advisory label? | 61a21c563cd5f615 | 1 | 8 | 0.0000 | dense-wins |
| mh-5a7dec305542995ed0d16679 | Which American filmmaker has directed more films, Jon Paul Puno or Ken Kwapis? | 27d48f75de236637 | 1 | 1 | 0.0141 | neither |
| mh-5a7dec305542995ed0d16679 | Which American filmmaker has directed more films, Jon Paul Puno or Ken Kwapis? | cc53e5164fef9858 | 2 | 2 | 0.0143 | neither |
| mh-5a7f39d055429934daa2fd2a | Which is a comedy film, The Million Dollar Duck or Don Quixote? | 1778d72c6f18d9f4 | 3 | 1 | 0.0127 | neither |
| mh-5a7f39d055429934daa2fd2a | Which is a comedy film, The Million Dollar Duck or Don Quixote? | dfaefd7a06c08d99 | 1 | 6 | 0.0000 | dense-wins |
| mh-5a7f87755542994857a76769 | Belle Gold is a fictional character portrayed by an actress of what nationality? | a035f8de6abca5ea | 1 | 1 | 0.0114 | neither |
| mh-5a7f87755542994857a76769 | Belle Gold is a fictional character portrayed by an actress of what nationality? | a8888c7a9b1f5078 | 4 | — | 0.0000 | dense-wins |
| mh-5a80ae105542992bc0c4a7a2 | What occupation is shared by both Marge Piercy and Richard Aldington? | 694f32be6d0ff2e3 | 1 | 3 | 0.0000 | dense-wins |
| mh-5a80ae105542992bc0c4a7a2 | What occupation is shared by both Marge Piercy and Richard Aldington? | e23df64ed1e8371e | 2 | 1 | 0.0161 | neither |
| mh-5a820c0c554299676cceb1fc | What is the name of the company that wholly owns the Value Alliance airline whose head office is within Terminal 2 of Narita International Airport? | 0331558ba35c1ee2 | 2 | 1 | 0.0152 | neither |
| mh-5a820c0c554299676cceb1fc | What is the name of the company that wholly owns the Value Alliance airline whose head office is within Terminal 2 of Narita International Airport? | c1fc0cd5a03587c0 | 1 | 6 | 0.0000 | dense-wins |
| mh-5a824858554299676cceb247 | What nationality was the noble house that employed Frntisek Rint to organize the human bones interred at the Sedlec Ossuary? | cc76c4f246c9b2d2 | 3 | 6 | 0.0000 | dense-wins |
| mh-5a824858554299676cceb247 | What nationality was the noble house that employed Frntisek Rint to organize the human bones interred at the Sedlec Ossuary? | f6fa0bb7e8f9c3a2 | 1 | 1 | 0.0156 | neither |
| mh-5a8333115542993344745feb | What summit is located in the county who's county seat is Helena? | a02751e4ff4c0e04 | 4 | 9 | 0.0000 | dense-wins |
| mh-5a8333115542993344745feb | What summit is located in the county who's county seat is Helena? | ba4c5a853e28183c | 1 | 4 | 0.0000 | dense-wins |
| mh-5a83de04554299334474609f | The second studio album by The D.O.C was named as a reference to Charles Manson's idea of a Beatles' song which was a product of McCartney's attempt to create what kind of sound? | 3c5d6c35135e2221 | 2 | 6 | 0.0000 | dense-wins |
| mh-5a83de04554299334474609f | The second studio album by The D.O.C was named as a reference to Charles Manson's idea of a Beatles' song which was a product of McCartney's attempt to create what kind of sound? | 833a252a93981768 | 1 | 5 | 0.0000 | dense-wins |
| mh-5a8434445542996488c2e517 | Who has released more solo albums, Ozzy Osbourne or Curt Smith? | 8f10d3fb88db2d40 | 1 | 2 | 0.0147 | dense-wins |
| mh-5a8434445542996488c2e517 | Who has released more solo albums, Ozzy Osbourne or Curt Smith? | be588ec823b46e3d | 2 | 1 | 0.0159 | neither |
| mh-5a84b5975542991dd0999da3 | In what ecclesiastical province is Stephen Conway currently part of? | 18c31b8cc658272f | 3 | 7 | 0.0000 | dense-wins |
| mh-5a84b5975542991dd0999da3 | In what ecclesiastical province is Stephen Conway currently part of? | 35646a9c0e3fd112 | 1 | 1 | 0.0141 | neither |
| mh-5a84e61b5542997b5ce3ff86 | The Simpsons episode that aired on February 19, 2012 entitled "At Long Last Leave" represented what milestone for the show? | 11807ee2e8126ad9 | 2 | 1 | 0.0164 | neither |
| mh-5a84e61b5542997b5ce3ff86 | The Simpsons episode that aired on February 19, 2012 entitled "At Long Last Leave" represented what milestone for the show? | b12fcbce07af0aa6 | 1 | — | 0.0000 | dense-wins |
| mh-5a85a2845542997175ce1fe1 | Are both Aloinopsis and Eriogonum ice plants? | 4fa84c714eced2a2 | 2 | 2 | 0.0164 | neither |
| mh-5a85a2845542997175ce1fe1 | Are both Aloinopsis and Eriogonum ice plants? | fab0a312052eaacb | 1 | 1 | 0.0156 | neither |
| mh-5a85e24a5542994775f6067f | Are Hoodoo Gurus and Pierre Bouvier of the same nationality? | 9a6ed39729fd0c1a | 2 | 3 | 0.0000 | dense-wins |
| mh-5a85e24a5542994775f6067f | Are Hoodoo Gurus and Pierre Bouvier of the same nationality? | d14179029f4938f9 | 1 | 4 | 0.0000 | dense-wins |
| mh-5a86ac555542996432c571e4 | Are Glenn Bidmead and Jacob Hoggard both guitarist? | 25e6e523d3995014 | 1 | 1 | 0.0161 | neither |
| mh-5a86ac555542996432c571e4 | Are Glenn Bidmead and Jacob Hoggard both guitarist? | 48a3c3d3bf2558e6 | 2 | 2 | 0.0164 | neither |
| mh-5a8777395542996e4f3087f3 | Ai-Ling Lee is a Singaporean sound editor who worked on a biographical survival drama film directed by who? | 5af778b471f62f9d | 1 | 1 | 0.0149 | neither |
| mh-5a8777395542996e4f3087f3 | Ai-Ling Lee is a Singaporean sound editor who worked on a biographical survival drama film directed by who? | 74bd0fa0de299d80 | 9 | — | 0.0000 | dense-wins |
| mh-5a8787915542996e4f30882e | Which film was produced first, Dangal or The Man from Snowy River II? | 2df3574b3063ef16 | 1 | 1 | 0.0104 | neither |
| mh-5a8787915542996e4f30882e | Which film was produced first, Dangal or The Man from Snowy River II? | 940349b7348db7f4 | 3 | — | 0.0000 | dense-wins |
| mh-5a87c6a75542997e5c09a56f | The Huskies football team were invited to the Alamo Bowl where they were defeated by a team coached by Art Briles and who played their home games at what statium? | e7f4368040fc706a | 1 | 1 | 0.0161 | neither |
| mh-5a87c6a75542997e5c09a56f | The Huskies football team were invited to the Alamo Bowl where they were defeated by a team coached by Art Briles and who played their home games at what statium? | f91d8b33f244eda0 | 2 | 9 | 0.0118 | dense-wins |
| mh-5a888c9d5542997e5c09a612 | Who is from farther west, Halestorm or Audioslave? | 0330c6812860b100 | 2 | 1 | 0.0156 | neither |
| mh-5a888c9d5542997e5c09a612 | Who is from farther west, Halestorm or Audioslave? | aacc8de439e85e80 | 1 | 2 | 0.0147 | dense-wins |
| mh-5a8a40015542996c9b8d5e72 | Which television series was part of Cartoon Network's 2017 April Fools' prank and had a song by Justin Roiland played during the third season of the same show? | 3b68974478b3a094 | 1 | 7 | 0.0000 | dense-wins |
| mh-5a8a40015542996c9b8d5e72 | Which television series was part of Cartoon Network's 2017 April Fools' prank and had a song by Justin Roiland played during the third season of the same show? | ff8ed382963bd999 | 2 | 10 | 0.0000 | dense-wins |
| mh-5a8a410655429970aeb70279 | Pyotr Verzilov is married to a Russian conceptual artist and what kind of activist? | 4c421cafb8811d99 | 2 | 6 | 0.0000 | dense-wins |
| mh-5a8a410655429970aeb70279 | Pyotr Verzilov is married to a Russian conceptual artist and what kind of activist? | 8ff4a7bf4ae545e8 | 1 | 1 | 0.0147 | neither |
| mh-5a8ae61955429970aeb70326 | Are both Deerhunter and Nine Lashes American Christian rock bands? | 57da3e9fa8646317 | 3 | 2 | 0.0159 | neither |
| mh-5a8ae61955429970aeb70326 | Are both Deerhunter and Nine Lashes American Christian rock bands? | b2b1dc146da862c2 | 1 | 1 | 0.0161 | neither |
| mh-5a8b77705542995d1e6f13aa | What American broadcasting company broadcasted the comedy show hosted by Emma Willmann? | a5199661aff3f82d | — | 7 | 0.0120 | **graph-win** |
| mh-5a8b77705542995d1e6f13aa | What American broadcasting company broadcasted the comedy show hosted by Emma Willmann? | bf8236283568c9f3 | 1 | 1 | 0.0161 | neither |
| mh-5a8c493e554299653c1aa020 | John ruskin named his album due to a removal of what? | 1895726a0a9119fb | — | — | 0.0000 | neither |
| mh-5a8c493e554299653c1aa020 | John ruskin named his album due to a removal of what? | f37978e089be5fbe | 4 | — | 0.0000 | dense-wins |
| mh-5a8c49655542995e66a47598 | Which college was founded first, Williams College or University of Southern California? | 9e06b365cc4f6db5 | 1 | 1 | 0.0135 | neither |
| mh-5a8c49655542995e66a47598 | Which college was founded first, Williams College or University of Southern California? | b2c199110b1c616f | 2 | 3 | 0.0115 | dense-wins |
| mh-5a8da1815542994ba4e3dcd7 | Naseer & Shahab is a Pakistani band playing a genre that dominated radio in what decade? | 43f3199ac95c47b0 | 1 | 1 | 0.0152 | neither |
| mh-5a8da1815542994ba4e3dcd7 | Naseer & Shahab is a Pakistani band playing a genre that dominated radio in what decade? | a14ae039c63091d8 | — | 3 | 0.0103 | **graph-win** |
| mh-5a8dee2455429917b4a5bce1 | What other film did the star of 127 Hours act in? | 34223e1d43f1b928 | 1 | 1 | 0.0145 | neither |
| mh-5a8dee2455429917b4a5bce1 | What other film did the star of 127 Hours act in? | fdbbe25550cc8ed4 | 3 | 6 | 0.0000 | dense-wins |
| mh-5a8ed7b455429917b4a5bdd1 | Rob is an American sitcom that starred what American actress who was best known for portraying Yolanda Saldivar in the film Selena? | 58ea94b41542ffd8 | 2 | — | 0.0000 | dense-wins |
| mh-5a8ed7b455429917b4a5bdd1 | Rob is an American sitcom that starred what American actress who was best known for portraying Yolanda Saldivar in the film Selena? | 8b1ce688bb416e6b | 1 | 9 | 0.0000 | dense-wins |
| mh-5a906c795542990a98493640 | What has David Bowie done in The Lodge? | ca690490a8022826 | 1 | 1 | 0.0152 | neither |
| mh-5a906c795542990a98493640 | What has David Bowie done in The Lodge? | cdeb4745e17046b4 | 2 | 2 | 0.0149 | neither |
| mh-5ab204795542993be8fa98ad | Peter and the Wolf was originally released as a segment of an animated anthology released to theaters on which day ? | 507188da4c072a07 | 1 | 1 | 0.0154 | neither |
| mh-5ab204795542993be8fa98ad | Peter and the Wolf was originally released as a segment of an animated anthology released to theaters on which day ? | fc9a3ce11325c3b7 | — | 8 | 0.0000 | fused-only (no graph) |
| mh-5ab28a87554299449642c8ec | This expansion of the 2008 magazine article "Is Google Making Us Stoopid?" was a finalist for what award? | 4fbf1a92389604bf | 1 | 1 | 0.0143 | neither |
| mh-5ab28a87554299449642c8ec | This expansion of the 2008 magazine article "Is Google Making Us Stoopid?" was a finalist for what award? | 8cc0ae9e562412d6 | 2 | 3 | 0.0141 | dense-wins |
| mh-5ab29486554299545a2cf9a4 | Which has more members, Dada or Alt-J? | efe743b20680d980 | 2 | 7 | 0.0000 | dense-wins |
| mh-5ab29486554299545a2cf9a4 | Which has more members, Dada or Alt-J? | fea07493137cb936 | 1 | 2 | 0.0000 | dense-wins |
| mh-5ab42e55554299753aec5a53 | San Marco and Medina are both what type of game? | 30d5ac78563031b4 | 1 | 9 | 0.0000 | dense-wins |
| mh-5ab42e55554299753aec5a53 | San Marco and Medina are both what type of game? | e9ff83f738971816 | 2 | 2 | 0.0130 | neither |
| mh-5ab5627b5542992aa134a2ff | How many members did Joseph Yablonski's union have in 2014? | 4bc1b05fb033046a | 2 | 1 | 0.0159 | neither |
| mh-5ab5627b5542992aa134a2ff | How many members did Joseph Yablonski's union have in 2014? | 82748bf7673f0e0b | 1 | 2 | 0.0149 | dense-wins |
| mh-5ab5e8935542997d4ad1f23b | Who proposed plan in which education in state institutions of Argentina is free at the initial, primary, secondary and tertiary levels and in the undergraduate university level? | 737a0f8c37e0583c | 1 | 3 | 0.0130 | dense-wins |
| mh-5ab5e8935542997d4ad1f23b | Who proposed plan in which education in state institutions of Argentina is free at the initial, primary, secondary and tertiary levels and in the undergraduate university level? | 8f89a90c858d94b8 | 2 | — | 0.0000 | dense-wins |
| mh-5ab6369655429953192ad2a1 | Which Genus has more species Eucryphia or Lepidozamia ? | 405316a100fff1f2 | 2 | 2 | 0.0143 | neither |
| mh-5ab6369655429953192ad2a1 | Which Genus has more species Eucryphia or Lepidozamia ? | bc8ea216cea779ab | 1 | 1 | 0.0139 | neither |
| mh-5ab681ea55429953192ad2e0 | Are Gael and Fitness published in the same country? | 72d4b5501ab415e6 | 3 | 4 | 0.0000 | dense-wins |
| mh-5ab681ea55429953192ad2e0 | Are Gael and Fitness published in the same country? | 9c6a51a93e195485 | 1 | 1 | 0.0000 | neither |
| mh-5ab71a6a5542991d3222377c | The debut album came out in 1988 but what year did the song "She's My Baby" come out in? | 3a5f61b740ab0108 | 1 | 2 | 0.0103 | dense-wins |
| mh-5ab71a6a5542991d3222377c | The debut album came out in 1988 but what year did the song "She's My Baby" come out in? | 8e1f41aef7b58fef | — | — | 0.0000 | neither |

## Extraction-yield note

Graph provenance of 0.0 in a fused result means the passage reached the top-10 exclusively through BM25 or dense paths; graph traversal contributed no candidates for that passage. A passage absent from fused results was not retrieved by any path.

