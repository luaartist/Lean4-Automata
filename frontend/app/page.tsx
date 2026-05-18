import Link from 'next/link';

export default function HomePage() {
  return (
    <div className="max-w-[1120px] mx-auto">
      <section className="grid grid-cols-1 xl:grid-cols-[1fr_420px] gap-32 items-start py-32">
        <div>
          <p className="text-sm font-semibold text-accent-primary mb-12">
            Lean 4 proof observability
          </p>
          <h1 className="text-[48px] leading-tight font-bold mb-16">
            Lean4-Automata
          </h1>
          <p className="text-lg text-text-secondary max-w-3xl mb-24">
            A local proof observatory for Lean 4 projects. Map imports, search
            symbols, track proof completion, record audit tickets, and preserve
            evidence badges for work that should remain inspectable over time.
          </p>
          <div className="flex flex-wrap gap-12">
            <Link
              href="/projects/1"
              className="px-16 py-12 bg-accent-primary text-white rounded font-semibold hover:bg-accent-hover transition-colors"
            >
              Open current Lean project
            </Link>
            <Link
              href="/search"
              className="px-16 py-12 bg-bg-surface border border-border rounded font-semibold hover:border-accent-primary transition-colors"
            >
              Search symbols
            </Link>
          </div>
        </div>

        <aside className="bg-bg-surface border border-border rounded p-20">
          <h2 className="text-xl font-semibold mb-12">What It Preserves</h2>
          <dl className="space-y-14">
            <div>
              <dt className="font-semibold">Lean source state</dt>
              <dd className="text-sm text-text-secondary">
                Files, imports, symbols, toolchain context, and proof status.
              </dd>
            </div>
            <div>
              <dt className="font-semibold">Audit evidence</dt>
              <dd className="text-sm text-text-secondary">
                Tickets, readable summaries, raw JSON, and unresolved obligations.
              </dd>
            </div>
            <div>
              <dt className="font-semibold">Badge context</dt>
              <dd className="text-sm text-text-secondary">
                Keepsake, public, and sovereign evidence classes with explicit
                contract boundaries.
              </dd>
            </div>
          </dl>
        </aside>
      </section>

      <section className="py-24 border-t border-border">
        <h2 className="text-2xl font-bold mb-16">Core Workflows</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-16">
          {workflows.map((item) => (
            <article
              key={item.title}
              className="bg-bg-surface border border-border rounded p-16"
            >
              <h3 className="font-semibold mb-8">{item.title}</h3>
              <p className="text-sm text-text-secondary">{item.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="py-24 border-t border-border">
        <h2 className="text-2xl font-bold mb-16">Proof And Evidence Boundary</h2>
        <div className="overflow-x-auto border border-border rounded bg-bg-surface">
          <table className="w-full text-sm">
            <thead className="bg-bg-secondary text-left">
              <tr>
                <th className="p-12 font-semibold">Artifact</th>
                <th className="p-12 font-semibold">What It Can Mean</th>
                <th className="p-12 font-semibold">What It Must Not Claim</th>
              </tr>
            </thead>
            <tbody>
              {boundaries.map((item) => (
                <tr key={item.artifact} className="border-t border-border">
                  <td className="p-12 font-semibold">{item.artifact}</td>
                  <td className="p-12 text-text-secondary">{item.canMean}</td>
                  <td className="p-12 text-text-secondary">{item.mustNot}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="py-24 border-t border-border">
        <h2 className="text-2xl font-bold mb-16">Packaging Surfaces</h2>
        <p className="text-text-secondary max-w-3xl mb-16">
          The package separates public presentation, local workbench use,
          Hugging Face preview, and internal operator tools. Wolfram companion
          maps remain optional and do not replace Lean verification. The
          repo-level static page lives at public/index.html for filesystem or
          static-hosting use.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-16">
          {surfaces.map((item) => (
            <article
              key={item.name}
              className="bg-bg-surface border border-border rounded p-16"
            >
              <h3 className="font-semibold mb-8">{item.name}</h3>
              <p className="text-sm text-text-secondary mb-8">{item.description}</p>
              <code className="text-xs text-text-secondary">{item.path}</code>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

const workflows = [
  {
    title: 'Choose a proof target',
    description:
      'Start with what you are proving and which Lean module or theorem should be treated as the main target.',
  },
  {
    title: 'Map source and imports',
    description:
      'Inspect Lean files, Mathlib references, external imports, and project-local dependency paths before changing the proof structure.',
  },
  {
    title: 'Record audit evidence',
    description:
      'Run audit flows, keep ticketed outputs, and issue only the badge class whose evidence contract is actually satisfied.',
  },
];

const boundaries = [
  {
    artifact: 'Lean build',
    canMean: 'Lean accepted the project under a specific toolchain.',
    mustNot: 'Independent peer review or publication acceptance.',
  },
  {
    artifact: 'Audit ticket',
    canMean: 'A named audit flow ran and produced structured output.',
    mustNot: 'Every finding is resolved.',
  },
  {
    artifact: 'Evidence badge',
    canMean: 'The stored L2BL4 contract currently passes for its class.',
    mustNot: 'A replacement for Lean verification.',
  },
];

const surfaces = [
  {
    name: 'Live Next workbench',
    description: 'Project overview, symbol search, module metrics, and graph navigation.',
    path: 'frontend/app',
  },
  {
    name: 'Static public page',
    description: 'No-CDN public overview that opens from disk or static hosting.',
    path: 'public/index.html',
  },
  {
    name: 'Hugging Face preview',
    description: 'Read-only public presentation surface for Spaces.',
    path: 'app.py',
  },
  {
    name: 'Offline internal dashboard',
    description: 'Local artifact navigator for maintainers without service calls.',
    path: 'ui/offline_internal.html',
  },
];
