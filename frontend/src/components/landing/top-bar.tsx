import Link from "next/link";
import { SiteHeader } from "@/components/shell/site-header";
import { cta } from "./cta";

/**
 * The landing uses the product's own header so the chrome does not change when "Open dashboard" is clicked.
 * Its action slot holds the ink-filled "Open dashboard"; the hero's filled CTA stays the only other one in view.
 */
export function TopBar() {
  return (
    <SiteHeader
      actions={
        <Link href="/overview" className={cta("secondary", "nav")}>
          Open dashboard
        </Link>
      }
    />
  );
}
