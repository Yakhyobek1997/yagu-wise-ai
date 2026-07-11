import { Nav } from "@/components/landing/Nav";
import { Hero } from "@/components/landing/Hero";
import { HardwareGate } from "@/components/landing/HardwareGate";
import { SystemStatus } from "@/components/landing/SystemStatus";
import { Features } from "@/components/landing/Features";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { Differentiators } from "@/components/landing/Differentiators";
import { Stack } from "@/components/landing/Stack";
import { CTA } from "@/components/landing/CTA";
import { Footer } from "@/components/landing/Footer";

export default function Landing() {
  return (
    <div className="min-h-screen">
      <Nav />
      <main>
        <Hero />
        {/* Hardware consent → scan → model recommendations */}
        <HardwareGate />
        <div className="px-4 md:px-6">
          <SystemStatus />
        </div>
        <Features />
        <HowItWorks />
        <Differentiators />
        <Stack />
        <CTA />
      </main>
      <Footer />
    </div>
  );
}
