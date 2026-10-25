import styles from "./marketing.module.css";

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className={`${styles.landing} flex min-h-screen flex-col overflow-x-clip bg-background text-foreground`}>
      {children}
    </div>
  );
}
