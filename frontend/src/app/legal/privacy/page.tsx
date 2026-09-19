import type { Metadata } from "next";
import PageClient from "./PageClient";

export const metadata: Metadata = {
  title: "Privacy policy",
};

export default function Page() {
  return <PageClient />;
}
