# Ordered parent lookup conformance

**Goal** Verify that a verb on the first parent's parent takes precedence over a verb on the second parent for ordinary calls and `pass()`.

**State** The focused managed session selected capability admission and the new audit case. Stock Toast and fixed Barn each reported `2 passed`. Baseline Barn reported `1 failed, 1 passed` and returned `[right, right, right, right]` where the test requires `[deep, right, deep, right]`.

**Decisions and why** The same graph yields the opposite result when the child has its parent list reversed. A `finally` block recycles the graph in child-first order.

**Surprises** The existing immediate-parent assertions cannot distinguish a depth-first walk from a breadth-first walk.

**Next step** Publish the test branch for review.
