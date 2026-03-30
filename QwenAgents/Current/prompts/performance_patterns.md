# Performance Patterns for Text-Heavy Web UIs

Universal patterns extracted from Pretext's architecture, generalized for any web project. These are not Pretext-specific -- they apply to any component that measures, renders, or manipulates text in the DOM.

---

## 1. Two-Phase Pattern

**Problem:** Mixing expensive computation with rendering creates jank. A component that calculates layout AND renders in the same pass blocks the main thread.

**Pattern:** Split work into two phases: **prepare** (pure computation, no DOM) and **render** (DOM writes only, no computation).

```typescript
// Phase 1: PREPARE (off the render path, cacheable)
function prepareTextLayout(text: string, containerWidth: number): LayoutPlan {
  const words = tokenize(text);
  const lines = computeLineBreaks(words, containerWidth);
  const totalHeight = lines.length * lineHeight;
  return { lines, totalHeight, containerWidth };
}

// Phase 2: RENDER (fast, DOM-only)
function renderLayout(plan: LayoutPlan, container: HTMLElement): void {
  container.style.height = `${plan.totalHeight}px`;
  for (const line of plan.lines) {
    const lineEl = document.createElement('div');
    lineEl.textContent = line.text;
    container.appendChild(lineEl);
  }
}
```

**When to use:** Any component that transforms data before displaying it. Fetch+transform vs. render. Parse+layout vs. paint. Score+rank vs. list.

**When to skip:** Trivial renders where the "computation" is just setting `textContent`. The overhead of separating phases isn't worth it for a static label.

---

## 2. Measurement Caching

**Problem:** DOM measurements (`getBoundingClientRect()`, `offsetWidth`, `scrollHeight`) trigger forced reflow. Calling them repeatedly -- especially in loops -- destroys performance.

**Pattern:** Measure once, cache the result, invalidate only on resize or content change.

```typescript
class MeasurementCache {
  private cache = new Map<string, DOMRect>();
  private observer: ResizeObserver;

  constructor() {
    // Invalidate on resize -- NOT on scroll, NOT on every frame
    this.observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        this.cache.delete(entry.target.dataset.cacheKey!);
      }
    });
  }

  measure(element: HTMLElement, key: string): DOMRect {
    if (this.cache.has(key)) {
      return this.cache.get(key)!;
    }
    const rect = element.getBoundingClientRect();
    this.cache.set(key, rect);
    element.dataset.cacheKey = key;
    this.observer.observe(element);
    return rect;
  }
}
```

**When to use:** Any component that reads DOM geometry more than once per user action. Tooltip positioning, text overflow detection, dynamic grid layouts.

**When to skip:** One-shot measurements (measure on mount, never again). The cache overhead isn't worth it if you measure once.

---

## 3. Virtualization

**Problem:** Rendering 10,000 items into the DOM is slow. Even if the browser can handle it, initial paint time and memory usage are unacceptable.

**Pattern:** Only render items visible in the viewport. Predict heights instead of measuring every item.

```typescript
interface VirtualItem {
  index: number;
  text: string;
  estimatedHeight: number; // predicted, not measured
}

function virtualizeList(
  items: string[],
  scrollTop: number,
  viewportHeight: number,
  avgItemHeight: number = 24 // prediction, not measurement
): VirtualItem[] {
  const startIndex = Math.floor(scrollTop / avgItemHeight);
  const visibleCount = Math.ceil(viewportHeight / avgItemHeight) + 2; // +2 buffer
  const endIndex = Math.min(startIndex + visibleCount, items.length);

  return items.slice(startIndex, endIndex).map((text, i) => ({
    index: startIndex + i,
    text,
    estimatedHeight: avgItemHeight,
  }));
}

// Spacer element above and below visible items fakes scroll height
// topSpacer.height = startIndex * avgItemHeight
// bottomSpacer.height = (items.length - endIndex) * avgItemHeight
```

**When to use:** Lists with 100+ items. Tables with 50+ rows. Any scrollable container where most content is offscreen.

**When to skip:** Short lists (under 50 items). The complexity of virtualization outweighs the performance gain. Also skip if items have wildly different heights and you can't predict them -- the scroll position jumps will annoy users more than the performance cost.

---

## 4. Batch DOM Reads

**Problem:** Interleaving DOM reads and writes causes layout thrashing. Each read after a write forces the browser to recalculate layout synchronously.

```typescript
// BAD: read-write-read-write (4 forced reflows)
const h1 = el1.offsetHeight;  // read -> reflow
el1.style.height = '100px';   // write (invalidates layout)
const h2 = el2.offsetHeight;  // read -> FORCED reflow
el2.style.height = '200px';   // write (invalidates layout)
```

**Pattern:** Batch all reads in one pass, then all writes in the next.

```typescript
// GOOD: read-read-write-write (1 reflow total)
const h1 = el1.offsetHeight;  // read
const h2 = el2.offsetHeight;  // read (no reflow, layout still valid)
el1.style.height = '100px';   // write
el2.style.height = '200px';   // write (batched, single reflow on next frame)

// For complex cases, use requestAnimationFrame to separate phases:
function batchUpdate(elements: HTMLElement[]) {
  // READ PHASE
  const measurements = elements.map(el => ({
    el,
    height: el.offsetHeight,
    width: el.offsetWidth,
  }));

  // WRITE PHASE (deferred to next frame)
  requestAnimationFrame(() => {
    for (const m of measurements) {
      m.el.style.transform = `translateY(${m.height}px)`;
    }
  });
}
```

**When to use:** Any code that reads and writes DOM properties for multiple elements. Especially: animation loops, resize handlers, drag-and-drop, dynamic layouts.

**When to skip:** Single-element updates where you read one property and write one property. The overhead of `requestAnimationFrame` scheduling isn't worth it for a single element.

---

## 5. Resize Debouncing

**Problem:** Window resize fires dozens of events per second. Re-running layout calculations on every event creates visible jank and wasted CPU cycles.

**Pattern:** Debounce resize handlers. If computation is cached (Pattern 2), the re-layout after debounce is cheap.

```typescript
function debounceResize(
  callback: () => void,
  delay: number = 150
): () => void {
  let timeout: number | null = null;

  const handler = () => {
    if (timeout) cancelAnimationFrame(timeout);
    // Use rAF instead of setTimeout for smoother visual updates
    timeout = requestAnimationFrame(() => {
      // Additional delay to let resize "settle"
      setTimeout(callback, delay);
    });
  };

  window.addEventListener('resize', handler, { passive: true });
  return () => window.removeEventListener('resize', handler);
}

// Usage
const cleanup = debounceResize(() => {
  measurementCache.invalidateAll();
  relayout();
}, 150);
```

**When to use:** Any component that recalculates layout on window resize. Responsive grids, text reflow, chart resizing.

**When to skip:** Components that use pure CSS for responsiveness (media queries, flexbox, grid). If the browser handles the resize via CSS, adding JS debouncing is redundant overhead.

---

## 6. Font Loading Strategy

**Problem:** Custom fonts load asynchronously. Before they arrive, the browser either shows invisible text (FOIT -- Flash of Invisible Text) or shows fallback text that jumps when the font loads (FOUT -- Flash of Unstyled Text). Both cause layout shift.

**Pattern:** Use `font-display: swap` to show fallback text immediately, then use `document.fonts.ready` to re-measure after the real font loads.

```css
/* CSS: Show fallback immediately, swap when loaded */
@font-face {
  font-family: 'Inter';
  src: url('/fonts/inter-var.woff2') format('woff2');
  font-display: swap;
}

/* Size-adjust the fallback to minimize shift */
@font-face {
  font-family: 'Inter-fallback';
  src: local('Arial');
  size-adjust: 107%;        /* match Inter's metrics */
  ascent-override: 90%;
  descent-override: 22%;
  line-gap-override: 0%;
}

body {
  font-family: 'Inter', 'Inter-fallback', sans-serif;
}
```

```typescript
// JS: Re-measure after font loads (for dynamic layouts)
document.fonts.ready.then(() => {
  // Font is loaded -- cached measurements are now stale
  measurementCache.invalidateAll();
  relayout();
});

// Or target a specific font:
document.fonts.load('16px Inter').then(() => {
  relayout();
});
```

**When to use:** Any project using custom web fonts where text drives layout (cards, grids, truncation). Critical for components that measure text width (e.g., auto-sizing inputs, text truncation with ellipsis).

**When to skip:** System font stacks only (`-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`). No custom fonts = no loading problem.

---

## 7. Avoid Layout Shift

**Problem:** Content that changes size after initial render causes Cumulative Layout Shift (CLS). Text is a major offender: font loading, dynamic content, and async data all change text dimensions after the user sees the initial layout.

**Pattern:** Reserve space for text before it loads. Use CSS to stabilize dimensions. Use Pretext or `min-height` for dynamic content.

```css
/* Reserve space with min-height based on expected content */
.card-title {
  min-height: 1.5em;     /* one line minimum */
  line-height: 1.5;
}

.card-description {
  min-height: 4.5em;     /* three lines minimum */
  line-height: 1.5;
}

/* For images/media that affect text flow */
.hero-image {
  aspect-ratio: 16 / 9;  /* reserves space before image loads */
  width: 100%;
}

/* Skeleton placeholder while loading */
.text-skeleton {
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 4px;
  height: 1em;
  width: 80%;
}
```

```typescript
// For dynamic text that arrives async:
function reserveSpace(container: HTMLElement, expectedLines: number) {
  const lineHeight = parseFloat(getComputedStyle(container).lineHeight);
  container.style.minHeight = `${expectedLines * lineHeight}px`;
}

// After text loads, remove the reservation:
function fillAndRelease(container: HTMLElement, text: string) {
  container.textContent = text;
  container.style.minHeight = '';  // let natural height take over
}
```

**When to use:** Any component where text arrives after initial render (API responses, lazy loading, skeleton screens). Also: components with dynamic text that changes length (counters, live data, user-generated content).

**When to skip:** Static pages where all text is in the HTML payload (SSR/SSG with no client-side text changes). If the text is in the initial HTML, the browser handles layout in one pass.

---

## Pattern Relationships

These patterns compose. A well-built text component typically uses several together:

```
[Font Loading (6)] -> invalidates -> [Measurement Cache (2)]
[Resize (5)]       -> invalidates -> [Measurement Cache (2)]
[Measurement Cache (2)] -> feeds -> [Two-Phase Prepare (1)]
[Two-Phase Prepare (1)] -> outputs -> [Layout Plan]
[Layout Plan] -> consumed by -> [Batch DOM Writes (4)]
[Virtualization (3)] -> reduces -> [Batch DOM Writes (4)] scope
[Layout Shift (7)] -> stabilized by -> [Two-Phase Prepare (1)] + [Font Loading (6)]
```

Start with Pattern 4 (Batch DOM Reads) -- it's the lowest effort, highest impact change. Add patterns as profiling reveals bottlenecks.
