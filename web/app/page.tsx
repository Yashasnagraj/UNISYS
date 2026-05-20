import { LandingNav } from "@/components/landing/nav";
import { LandingHero } from "@/components/landing/hero";
import { LandingProblem } from "@/components/landing/problem";
import { LandingHowItWorks } from "@/components/landing/how-it-works";
import { LandingDemoCta } from "@/components/landing/demo-cta";
import { LandingTeam } from "@/components/landing/team";
import { LandingFooter } from "@/components/landing/footer";

export default function Home() {
  return (
    <div className="relative flex min-h-screen flex-col bg-bg-primary">
      <LandingNav />
      <main className="flex-1">
        <LandingHero />
        <LandingProblem />
        <LandingHowItWorks />
        <LandingDemoCta />
        <LandingTeam />
      </main>
      <LandingFooter />
    </div>
  );
}
