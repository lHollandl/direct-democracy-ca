import type { Metadata } from "next";
import PageClient from "./PageClient";

export const metadata: Metadata = {
  title: "Your account",
};

export default function Page() {
  return <PageClient />;
}
