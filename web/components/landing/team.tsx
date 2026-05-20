const MEMBERS = [
  { name: "Yashas N",                department: "AI & Data Science",      role: "Software & AI" },
  { name: "Jeeth Kataria",           department: "AI & Data Science",      role: "Hardware & DSP" },
  { name: "Naveen G Patil",          department: "AI & Machine Learning",  role: "ML Engineering" },
  { name: "Project Member",          department: "TBD",                    role: "Clinical Studies" },
];

const GUIDE = {
  name: "Dr. Sowmya B. J.",
  department: "AI & Data Science · Associate Professor",
  role: "Project Guide",
};

export function LandingTeam() {
  return (
    <section id="team" className="px-6 py-24 md:px-12">
      <div className="mx-auto max-w-5xl">
        <div className="mb-12 max-w-2xl">
          <div className="text-[11px] uppercase tracking-[0.16em] text-text-faint">
            The team
          </div>
          <h2 className="mt-2 font-display text-3xl font-semibold text-text md:text-4xl">
            Built at Ramaiah Institute of Technology.
          </h2>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {MEMBERS.map((m) => <Member key={m.name} {...m} />)}
        </div>
        <div className="mt-6">
          <Member {...GUIDE} highlight />
        </div>
      </div>
    </section>
  );
}

function Member({ name, department, role, highlight = false }: {
  name: string; department: string; role: string; highlight?: boolean;
}) {
  const initials = name.split(" ").filter(Boolean).map((s) => s[0]).slice(0, 2).join("").toUpperCase();
  return (
    <div className={"surface p-5 " + (highlight ? "border-accent/30" : "")}>
      <div className="flex items-center gap-3">
        <span
          className={
            "flex h-11 w-11 items-center justify-center rounded-full font-mono text-sm font-semibold " +
            (highlight ? "bg-accent text-[#001619]" : "bg-bg-elevated text-text")
          }
        >
          {initials}
        </span>
        <div className="leading-tight">
          <div className="font-display text-[14.5px] font-semibold text-text">{name}</div>
          <div className="text-[11px] text-text-faint">{department}</div>
        </div>
      </div>
      <div className="mt-3 text-[11px] uppercase tracking-[0.14em] text-accent">{role}</div>
    </div>
  );
}
