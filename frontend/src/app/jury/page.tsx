import type { Metadata } from "next";
import PageClient from "./PageClient";

export const metadata: Metadata = {
  title: "Jury duty",
};

export default function Page() {
  return <PageClient />;
}
