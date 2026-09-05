# Independent households own separate private data

The first deployment serves one private household, with a future public service
intended to serve entirely separate households. Recipes, inventory, cooking
history, and grocery lists belong within a household boundary; there are no
relationships or sharing between households. This chooses household privacy
over a shared recipe community or a global workspace for all registered users.

The current app implements one shared household. Supporting unrelated households
requires enforcing this boundary before admitting them to the same service;
opening registration alone does not provide isolation. Multiple-household
implementation and overlapping-membership decisions are deferred until that
expansion begins; current deployment work serves only the owner's household.
This decision does not choose a database layout or roles.
