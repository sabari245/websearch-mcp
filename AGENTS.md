# Agent Instructions

you're not to impliment anything one your own but rather use the coding agent sub agent to impliment your spec

some instruction you might want to send the sub agents

* keep the implimentation minimal and clean, don't write any comments
* don't write tests and don't run the program

some of the things which you as the parent agent should do, test the code in three phases

* phase 1: skimming, go thorough it generally and see if there is any directly visible problem in the codebase, if so just reinstruct the subagent to fix it. either spin a second agent of use the previous instance itself to run it (if that kinda agent management is within your capability)
* phase 2: test the system manually to see if everything is working, if it is not send it to the subagent with the Instructions
* phase 3: once all the manual testing is done, update the README.md yourself (readme.md shall be the only thing that you'll write yourself) and hand over to the user.
