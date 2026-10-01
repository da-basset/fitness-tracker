import type { Note, Schedule } from '@/api/types';
import { ThemedText } from '@/components/themed-text';
import { Card, EmptyState, Loading, PageTitle, ResourceStatus, Screen, Section } from '@/components/ui';
import { fetchSchedule, SCHEDULE_KEY } from '@/data/training';
import { useResource } from '@/data/use-resource';

export default function NutritionScreen() {
  // Same cached response as the schedule, so it works offline too.
  const schedule = useResource<Schedule>(SCHEDULE_KEY, fetchSchedule);
  const data = schedule.data;

  return (
    <Screen refreshing={schedule.refreshing} onRefresh={schedule.refresh}>
      <PageTitle title="Nutrition" subtitle="From your trainer" />
      <ResourceStatus
        offline={schedule.offline}
        error={schedule.error}
        fetchedAt={schedule.fetchedAt}
        hasData={!!data}
      />
      {!data ? (
        schedule.loading ? (
          <Loading />
        ) : schedule.notFound ? (
          <EmptyState title="No plan yet" message="Nutrients and supplements come with your plan." />
        ) : null
      ) : (
        <>
          <NoteList title="Nutrients" notes={data.nutrients} empty="No nutrition targets yet." />
          <NoteList title="Supplements" notes={data.supplements} empty="No supplements recommended." />
        </>
      )}
    </Screen>
  );
}

function NoteList({ title, notes, empty }: { title: string; notes: Note[]; empty: string }) {
  return (
    <Section title={title}>
      {notes.length === 0 ? (
        <ThemedText type="small" themeColor="textSecondary">
          {empty}
        </ThemedText>
      ) : (
        notes.map((note) => (
          <Card key={note.id}>
            <ThemedText type="smallBold">
              {note.name}
              {note.amount ? <ThemedText type="small">{`  ${note.amount}`}</ThemedText> : null}
            </ThemedText>
            {note.timing ? (
              <ThemedText type="small" themeColor="textSecondary">
                {note.timing}
              </ThemedText>
            ) : null}
            {note.notes ? <ThemedText type="small">{note.notes}</ThemedText> : null}
          </Card>
        ))
      )}
    </Section>
  );
}
