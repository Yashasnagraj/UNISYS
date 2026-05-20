export function LandingHowItWorks() {
  return (
    <section id="how" className="px-6 py-24 md:px-12">
      <div className="mx-auto max-w-5xl">
        <div className="mb-12 max-w-2xl">
          <div className="text-[11px] uppercase tracking-[0.16em] text-text-faint">
            How it works
          </div>
          <h2 className="mt-2 font-display text-3xl font-semibold text-text md:text-4xl">
            Three steps, twenty seconds.
          </h2>
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          <Step
            n="01"
            title="Tap"
            body="A controlled vibration is sent through the skin into the bone using a precision voice-coil actuator."
          />
          <Step
            n="02"
            title="Listen"
            body="A medical-grade sensor on the opposite side records how the bone vibrates back — its unique resonant signature."
          />
          <Step
            n="03"
            title="Predict"
            body="The AI compares that signature to thousands of healing patterns and tells the surgeon exactly when the patient can walk."
          />
        </div>
      </div>
    </section>
  );
}

function Step({ n, title, body }: { n: string; title: string; body: string }) {
  return (
    <div className="relative">
      <div className="font-mono text-[12px] tracking-widest text-accent">{n}</div>
      <div className="my-3 h-px w-12 bg-accent" />
      <h3 className="font-display text-2xl font-semibold text-text">{title}</h3>
      <p className="mt-3 text-[13.5px] leading-relaxed text-text-muted">{body}</p>
    </div>
  );
}
