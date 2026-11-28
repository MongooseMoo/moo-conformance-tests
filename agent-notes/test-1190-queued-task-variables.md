# Queued task variables during read and suspend

## Goal

Cover MongooseMoo/barn#1190 with a managed conformance case.

## State

A worker publishes its task ID and blocks in read(). An observer checks the marker in field 11, sends a new value to the worker, and checks the updated marker after the worker calls suspend().

## Decisions and why

Use a second connection so the same foreground task can be observed in both waits without depending on the fork feature.

## Surprises

Baseline Barn raises E_RANGE on the first marker lookup. The case and admission pass on stock WSL Toast and the fixed Barn build.

## Next step

Land the Barn fix before this case joins the shared suite.
