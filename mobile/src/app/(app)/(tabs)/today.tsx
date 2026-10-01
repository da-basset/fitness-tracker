import { router } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import type { Schedule, ScheduleWeek, Weekday } from '@/api/types';
import { ThemedText } from '@/components/themed-text';
import {
  Banner,
  Card,
  Choice,
  ColorDot,
  EmptyState,
  Icon,
  Loading,
  PageTitle,
  ResourceStatus,
  Row,
  Screen,
  Section,
} from '@/components/ui';
import { Spacing } from '@/constants/theme';
import { formatLongDate } from '@/data/dates';
import { readCache, writeCache } from '@/data/db';
import { overlaySchedule } from '@/data/outbox';
import { fetchSchedule, SCHEDULE_KEY } from '@/data/training';
import { usePendingCount } from '@/data/use-pending';
import { useResource } from '@/data/use-resource';
import { useTheme } from '@/hooks/use-theme';

const SELECTED_WEEK_KEY = 'ui:selected-week';
const JS_WEEKDAYS: Weekday[] = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export default function TodayScreen() {
  const schedule = useResource<Schedule>(SCHEDULE_KEY, fetchSchedule, overlaySchedule);
  const pending = usePendingCount();
  const [weekId, setWeekId] = useState<number | null>(null);

  // Like the web page you pick the phase and week yourself; the app
  // remembers the last one you looked at.
  useEffect(() => {
    readCache<number>(SELECTED_WEEK_KEY).then((saved) => {
      if (saved) setWeekId(saved.data);
    });
  }, []);

  const data = schedule.data;
  const allWeeks = useMemo(() => data?.phases.flatMap((p) => p.weeks.map((w) => ({ phase: p, week: w }))) ?? [], [data]);
  const current = allWeeks.find((entry) => entry.week.id === weekId) ?? allWeeks[0];

  function selectWeek(id: number) {
    setWeekId(id);
    writeCache(SELECTED_WEEK_KEY, id);
  }

  if (!data) {
    return (
      <Screen refreshing={schedule.refreshing} onRefresh={schedule.refresh}>
        <PageTitle title="Today" />
        {schedule.loading ? (
          <Loading />
        ) : schedule.notFound ? (
          <EmptyState title="No plan yet" message="Your trainer hasn't assigned you a plan. Pull down to check again." />
        ) : (
          <ResourceStatus offline={schedule.offline} error={schedule.error} fetchedAt={null} hasData={false} />
        )}
      </Screen>
    );
  }

  const today = JS_WEEKDAYS[new Date().getDay()];

  return (
    <Screen refreshing={schedule.refreshing} onRefresh={schedule.refresh}>
      <PageTitle title={data.plan.name} subtitle={formatLongDate(data.date)} />
      <ResourceStatus offline={schedule.offline} error={schedule.error} fetchedAt={schedule.fetchedAt} hasData />
      {pending > 0 && (
        <Banner tone="info">
          {pending === 1 ? '1 change' : `${pending} changes`} saved on this phone, waiting to sync.
        </Banner>
      )}

      {data.phases.length === 0 ? (
        <EmptyState title="This plan has no phases yet" message="Your trainer is still building it." />
      ) : (
        current && (
          <>
            <Section title="Phase">
              <Choice
                options={data.phases.map((p) => ({ value: p.id, label: `${p.number}. ${p.title}` }))}
                value={current.phase.id}
                onChange={(phaseId) => {
                  const first = data.phases.find((p) => p.id === phaseId)?.weeks[0];
                  if (first) selectWeek(first.id);
                }}
              />
              {current.phase.note ? (
                <ThemedText type="small" themeColor="textSecondary" style={styles.note}>
                  {stripTags(current.phase.note)}
                </ThemedText>
              ) : null}
            </Section>

            {current.phase.weeks.length > 1 && (
              <Section title="Week">
                <Choice
                  options={current.phase.weeks.map((w) => ({ value: w.id, label: w.label }))}
                  value={current.week.id}
                  onChange={selectWeek}
                />
              </Section>
            )}

            <WeekTallyCard week={current.week} />

            <Section title={current.week.label}>
              {current.week.days.map((day) =>
                day.workout ? (
                  <Row
                    key={day.weekday}
                    leading={<ColorDot color={day.workout.color} />}
                    title={`${day.weekday === today ? 'Today' : day.weekday} · ${day.workout.name}`}
                    detail={day.workout.sub || null}
                    onPress={() =>
                      router.push({
                        pathname: '/workout/[workoutId]',
                        params: { workoutId: day.workout!.id, weekId: current.week.id },
                      })
                    }
                  />
                ) : (
                  <Row
                    key={day.weekday}
                    leading={<Icon name="moon.zzz" size={14} />}
                    title={`${day.weekday === today ? 'Today' : day.weekday} · Rest`}
                  />
                )
              )}
            </Section>
          </>
        )
      )}
    </Screen>
  );
}

function WeekTallyCard({ week }: { week: ScheduleWeek }) {
  const theme = useTheme();
  const { completed, total, week_complete } = week.week_tally;
  const ratio = total > 0 ? Math.min(1, completed / total) : 0;
  return (
    <Card>
      <View style={styles.tallyHeader}>
        <ThemedText type="smallBold">This week</ThemedText>
        <ThemedText type="smallBold" style={{ color: week_complete ? theme.success : theme.textSecondary }}>
          {week_complete ? 'Week complete' : `${completed} of ${total} workouts`}
        </ThemedText>
      </View>
      <View
        style={[styles.track, { backgroundColor: theme.backgroundSelected }]}
        accessibilityRole="progressbar"
        accessibilityValue={{ min: 0, max: total, now: completed }}>
        <View
          style={[
            styles.fill,
            { width: `${ratio * 100}%`, backgroundColor: week_complete ? theme.success : theme.accent },
          ]}
        />
      </View>
    </Card>
  );
}

/** Phase notes may carry simple HTML like <strong> from the web editor. */
function stripTags(html: string) {
  return html.replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&');
}

const styles = StyleSheet.create({
  note: { paddingHorizontal: Spacing.one },
  tallyHeader: { flexDirection: 'row', justifyContent: 'space-between' },
  track: { height: 8, borderRadius: 4, overflow: 'hidden' },
  fill: { height: 8, borderRadius: 4 },
});
