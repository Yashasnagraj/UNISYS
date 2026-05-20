export function LandingProblem() {
  return (
    <section className="border-t border-line bg-bg-panel px-6 py-24 md:px-12">
      <div className="mx-auto max-w-5xl">
        <div className="mb-12 max-w-2xl">
          <div className="text-[11px] uppercase tracking-[0.16em] text-text-faint">
            The problem
          </div>
          <h2 className="mt-2 font-display text-3xl font-semibold text-text md:text-4xl">
            The bone heals weeks before the X-ray catches up.
          </h2>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          <ProblemCard
            headline="X-ray shows calcium, not strength."
            body="A fracture regains mechanical stiffness 3–4 weeks before it looks healed on a film. Surgeons make the weight-bearing decision by feel."
          />
          <ProblemCard
            headline="₹25 lakh of equipment exists."
            body="The only devices that actually measure tissue stiffness cost between ₹15 and ₹35 lakh and live in major hospitals. Rural clinics see none of it."
          />
          <ProblemCard
            headline="1 in 5 fractures heal slowly."
            body="Delayed union or non-union affects 5–20% of fractures depending on bone and patient. Without a way to measure healing, surgeons learn too late."
          />
        </div>
      </div>
    </section>
  );
}

function ProblemCard({ headline, body }: { headline: string; body: string }) {
  return (
    <div className="surface p-6">
      <h3 className="font-display text-[17px] font-semibold leading-snug text-text">
        {headline}
      </h3>
      <p className="mt-3 text-[13.5px] leading-relaxed text-text-muted">{body}</p>
    </div>
  );
}
