Problem 2: Study the Campus Customs database
We are creating an agentic team to run our Campus Customs shop. There will be an MCP server, FastAPI backend, and React dashboard.
Look through every table and its fields in the data/campus_customs.db file. I have copied the original file to data/campus_customs_new.db. For this project, we will update the data/campus_customs_new.db file and leave data/campus_customs.db as is. Study the 3 open tickets to understand how they link to the other tables. 
Also create output/harness.md and list the fields and add 1 short line on why the table matters for the agents.

Problem 3: Build the MCP server
Now, create an MCP server in mcp_server using FastMCP. This will talk to data/campus_customs_new.db. Do not connect or run yet. Every agent uses the tools in this MCP server.
Write 3 tools needed for the tickets in the database. Keep the names clear to understand. DO NOT INVENT data.
List the 3 MCP tools in output/harness.md. For each, include which table it reads, which ticket it helps unlock (101,102,103) and one sentence on why that tool is right for that ticket. 
Also, create mcp_server/README.md that explains what the MCP server is for, which database file it uses and the 3 tools it has.

Problem 4: Add the MCP server to vibe coder and test each tool
Add the MCP server to hw5 so that Claude Code can call the tools. Save the connection JSON text in .mcp.json.
Once the vibecoder is connected, test each of the 3 MCP tools and save the evidence in output/mcp_smoke.json. For each tool, include:
the prompt you asked the vibe coder
the tool name
the tool output

Problem 5: Build the agent team and grow the MCP tools
Build an agentic team using PydancticAI: Boss, Inventory, Accounting, Facilities, and Customer Service. Include the prompts, models, and agent loops so tjey can delegate work to each other with full connectivity. 
Put the agent prompts in backend/prompts/ - one file per agent. Detailed prompts are better.
Put the data types in backend/models.py and the agnet files under backend/
Use the PORTKEY_API_KEY and only gpt-6-luna for all agents. 
Add tools to the MCP server so the agent can work on the open tickets. Shop facts come from the MCP server over data/campus_customs_new.db DO NOT INVENT A SECOND SHOP-TOOLS LAYER THAT BYPASSES THE MCP.
Wire the agents so they append to output/audit_trail.json as they run for each agent-loop step. Append to this file, do not wipe it each run.
In output/harness.md list each agent and MCP tool along eith which tables the tool uses. Also add a short safety section - the guardrails a real business would want when agents touch real customers and real money and limits that keep token use in check. Update the mpc_server/README.md so the tool list matches the changes.

Problem 6: Plan the three tickets
Before writing the backend, write down what you expect the team to do on each open ticket. Build output/desk_tickets.html a page you can double-click with one tab per ticket(101,102,103). add empty cash and reflection tabs for later. on each tab, fill an Expected section only (leave room for 'Actual' section).
For each ticket's expected section write down:
Who the boss should call first and why?
All the agent delegations you expect
Which MCP tools you expect that run to use

Problem 7: Backend Routes
In backend/main.py, use FASTAPI and add routes that do the following:
Return the 3 tickets and whether each is open or resolved
Take a ticket id and run your agent team on the ticket
Return recent agent events - what each agent said and which tools they used
Approve a payment or purchase after a human clicks approve (agents only prepare the payment, this route changes cash)
Return the current checking balance from cash_accounts
Reset the database to the original values when you want to try a fresh run.
From the backend/ folder, start the server with: uvicorn main:app --reload --port 8000
this turns on the backend at https://localhost:8000 so the frontend dashboard can call those routes.
In output/harness.md, list each route in one line (which url and what is does)

Problem 8: Agent dashboard
Build the front end dashboard with react, vite, and TypeScript. The page should call the routes we built previously. The dashboard should:
list all three tickets 
let me pick 1 ticket and start the agent team on it 
show each agent and what they are saying/ doing while the ticket runs 
mark a ticket resolved when the run finishes 
show a short summary of what each agent did on that ticket 
let a human approve a pay or purchase when asked 
show the checking balance (it should decrease when pay is approved).
Make the dashboard look good. Tell the front end to talk to the back end AT http://localhost:8000. On the back end allow the vite page origin (usually http://localhost:5173 )so the browser is allowed to call those routes. Start the dashboard with npm run dev. This will open the react app in the browser so I can pick tickets and watch the agents. start the board with npm run dev
Write output/design.md with what you chose for the dashboard look (layout, how agents read differently, how tickets and cash show up) and why including the creative choices that made it feel special and something humans would want to use.

Problem 9: Resolve the tickets
Reset the working database data/campus_customs_new.db so you can start clean. Note the starting checking balance.
Then run all three tickets on the board until each is resolved. Open output/desk_tickets.html and on each ticket tab fill the actual section from this run - which agents worked what they delegated and which tools they used. Keep the expected  section so you can compare the 2.
On the cash tab of output/desk_tickets.html, itemize the money:
starting checking balance after the reset 
for each ticket - how much cash changed when that ticket resolved and why 
ending checking balance - it must match cash accounts and working database
Also, save output/resolved_tickets.json - for each ticket: id, final status, short outcome, what each agent contributed and any human approvals 
And save output/resolved_board.html - page you can double click with a screenshot of react dashboard for each resolved ticket (101,102,103).
Append the runs to output/audit_trail.json and finish the output/harness.md so it covers the tables, MCP tools, 5 agents, API routs, the dashboard and safety rules.

Problem 10: Reflection
Open output/desk_ticket.html and fill the reflection tab with the following answers:How would you evaluate the performance of the agent on each ticket and why
For each ticket how did actual compared to the expected plan you wrote earlier
What would have been simpler as one agent with tools and why
Describe 3 new problems campus customs might face that this agent team could solve with the tools we've built
Describe 3 new problems campus custom might face that this agent team could not solve with the tools we built and explained the tools and agents We would need to solve them.
Tie answers to the ticket tabs and cash tab on the same page as evidence.