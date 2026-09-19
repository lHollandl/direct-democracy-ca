import type { Metadata } from "next";
import PageClient from "./PageClient";

export const metadata: Metadata = {
  title: "Terms of service",
};

export default function Page() {
  return <PageClient />;
}
