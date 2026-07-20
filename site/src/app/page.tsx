import { Hero } from "@/components/hero";
import { DemoVideo } from "@/components/demo-video";
import { ComparisonBars } from "@/components/comparison-bars";
import { SilenceQuote } from "@/components/silence-quote";
import { FeaturesBento } from "@/components/features-bento";
import { SettingsScreenshot } from "@/components/settings-screenshot";
import { OnboardingScreenshot } from "@/components/onboarding-screenshot";
import { Privacy } from "@/components/privacy";
import { GetStarted } from "@/components/get-started";

export default function Home() {
  return (
    <>
      <Hero />
      <DemoVideo />
      <ComparisonBars />
      <SilenceQuote />
      <FeaturesBento />
      <SettingsScreenshot />
      <OnboardingScreenshot />
      <Privacy />
      <GetStarted />
    </>
  );
}
