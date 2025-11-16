import DefaultLayout from "@/layouts/default";

export default function RecordingsPage() {
  return (
    <DefaultLayout>
      <section className="flex flex-col items-center justify-center gap-4 py-8 md:py-10">
        <div className="inline-block max-w-lg text-center justify-center">
          <h1>Recordings</h1>
        </div>
      </section>
    </DefaultLayout>
  );
}
