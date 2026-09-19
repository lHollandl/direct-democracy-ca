import type { Metadata } from "next";
import PageClient from "./PageClient";

export const metadata: Metadata = {
  title: "Choose a new password",
};

export default function Page() {
  return <PageClient />;
}
