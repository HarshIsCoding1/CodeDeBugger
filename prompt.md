we want to make a coding agent in oython which can solve simple bugs 
we will use grok llm for this . 

the llm will have some tools which will help in solving the bug 
one tool can be search files which lists the path of files which are related to the bug and we need ato search file tool which can give line numbers related to bug 
we need replace function which allows replcing a line with another 

tp test this , i wanna test this my self . prepare a simple .cpp file and write boiler plate code do not introrduce any bug now ill do it mnyself 

i want to give the bug in simple english in cli nand the llm and the tools should solve it . make the system without langraph and keep it simple /
also there will be max retry of 3 times . if the llm cant so;ve the bugs in the limit print a message saying it cant sol;ve it 

also there should be clear print statement saying which toolswere called on each step , we wanna understand the complete flow 

as soon as i change the cpp file and run the agent it should ask me my bug after i give my bug it should begin solving it 

dp not write any test case fpr now if anything is unclear as me 