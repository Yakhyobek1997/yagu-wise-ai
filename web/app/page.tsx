import { Nav } from "@/components/landing/Nav";
import { LandingShowcase } from "@/components/landing/LandingShowcase";
import { Features } from "@/components/landing/Features";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { Differentiators } from "@/components/landing/Differentiators";
import { CTA } from "@/components/landing/CTA";
import { Footer } from "@/components/landing/Footer";

export default function Landing() {
  return (
    <div className="min-h-screen bg-ink text-fg">
      <Nav />
      <main>
        <LandingShowcase />
        <Features />
        <HowItWorks />
        <Differentiators />
        <CTA />
      </main>
      <Footer />
    </div>
  );
}
