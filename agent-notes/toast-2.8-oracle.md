# Toast 2.8 expectation cutover

## Goal

Land the complete Toast 2.8 expectation data with the corresponding Barn
implementation group, after the trusted controller changes are on main.

## State

Refreshed #217 from main. The next CI failure rejected eight renamed durable
test identities. Restored those names while retaining the updated Toast 2.8
assertions and descriptions. No expectation or inventory check was weakened.

## Decisions and why

Names identify cases across candidate inventories and execution ledgers.
Some historical names describe old behavior; their current descriptions and
expected results describe the new oracle. Keep the existing Barn repeat-423
selector targeting that stable identity.

## Surprises

The original data update renamed cases, which the trusted inventory correctly
rejected as deleting coverage. The controller changes from #218 were already
on main and only needed integrating into this branch.

## Next step

Publish the restored identities, update from main after #220, and require
full Toast and paired Barn candidate evidence before merging.
