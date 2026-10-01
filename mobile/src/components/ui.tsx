import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import type { PropsWithChildren, ReactNode } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
  type StyleProp,
  type TextInputProps,
  type ViewStyle,
} from 'react-native';

import type { WorkoutColor } from '@/api/types';
import { ThemedText } from '@/components/themed-text';
import { MaxContentWidth, Spacing, WorkoutColors } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { useTheme } from '@/hooks/use-theme';

export function useWorkoutColor(color: WorkoutColor | string | undefined) {
  const scheme = useColorScheme() === 'dark' ? 'dark' : 'light';
  const palette = WorkoutColors[scheme];
  return palette[(color as WorkoutColor) ?? 'blue'] ?? palette.blue;
}

/** Scrollable page body with pull-to-refresh. */
export function Screen({
  children,
  refreshing,
  onRefresh,
  contentStyle,
}: PropsWithChildren<{ refreshing?: boolean; onRefresh?: () => void; contentStyle?: StyleProp<ViewStyle> }>) {
  const theme = useTheme();
  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: theme.background }}
      contentInsetAdjustmentBehavior="automatic"
      keyboardShouldPersistTaps="handled"
      contentContainerStyle={[styles.screen, contentStyle]}
      refreshControl={
        onRefresh ? <RefreshControl refreshing={!!refreshing} onRefresh={onRefresh} /> : undefined
      }>
      {children}
    </ScrollView>
  );
}

/** Large title for tab pages, which have no navigation header. */
export function PageTitle({ title, subtitle }: { title: string; subtitle?: string | null }) {
  return (
    <View style={styles.pageTitle}>
      <ThemedText type="subtitle">{title}</ThemedText>
      {subtitle ? <ThemedText themeColor="textSecondary">{subtitle}</ThemedText> : null}
    </View>
  );
}

export function Section({ title, action, children }: PropsWithChildren<{ title?: string; action?: ReactNode }>) {
  return (
    <View style={styles.section}>
      {(title || action) && (
        <View style={styles.sectionHeader}>
          {title ? (
            <ThemedText type="smallBold" themeColor="textSecondary" style={styles.sectionTitle}>
              {title}
            </ThemedText>
          ) : (
            <View />
          )}
          {action}
        </View>
      )}
      {children}
    </View>
  );
}

export function Card({ children, style }: PropsWithChildren<{ style?: StyleProp<ViewStyle> }>) {
  const theme = useTheme();
  return <View style={[styles.card, { backgroundColor: theme.backgroundElement }, style]}>{children}</View>;
}

export function Icon({ name, size = 18, color }: { name: SymbolViewProps['name']; size?: number; color?: string }) {
  const theme = useTheme();
  return <SymbolView name={name} size={size} tintColor={color ?? theme.textSecondary} />;
}

/** A tappable list row: title, optional detail line, optional accessory. */
export function Row({
  title,
  detail,
  onPress,
  accessory,
  leading,
  disabled,
}: {
  title: string;
  detail?: string | null;
  onPress?: () => void;
  accessory?: ReactNode;
  leading?: ReactNode;
  disabled?: boolean;
}) {
  const theme = useTheme();
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || !onPress}
      accessibilityRole={onPress ? 'button' : undefined}
      style={({ pressed }) => [
        styles.row,
        { backgroundColor: pressed ? theme.backgroundSelected : theme.backgroundElement },
      ]}>
      {leading}
      <View style={styles.rowText}>
        <ThemedText numberOfLines={2}>{title}</ThemedText>
        {detail ? (
          <ThemedText type="small" themeColor="textSecondary" numberOfLines={3}>
            {detail}
          </ThemedText>
        ) : null}
      </View>
      {accessory ?? (onPress ? <Icon name="chevron.right" size={14} /> : null)}
    </Pressable>
  );
}

export function ColorDot({ color, size = 12 }: { color: WorkoutColor | string; size?: number }) {
  const fill = useWorkoutColor(color);
  return <View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: fill }} />;
}

type ButtonProps = {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'destructive' | 'plain';
  disabled?: boolean;
  busy?: boolean;
  icon?: SymbolViewProps['name'];
  compact?: boolean;
};

export function Button({ title, onPress, variant = 'primary', disabled, busy, icon, compact }: ButtonProps) {
  const theme = useTheme();
  const palette = {
    primary: { bg: theme.accent, fg: theme.onAccent },
    secondary: { bg: theme.backgroundElement, fg: theme.text },
    destructive: { bg: theme.backgroundElement, fg: theme.danger },
    plain: { bg: 'transparent', fg: theme.accent },
  }[variant];
  const inactive = disabled || busy;
  return (
    <Pressable
      onPress={onPress}
      disabled={inactive}
      accessibilityRole="button"
      accessibilityState={{ disabled: !!inactive, busy: !!busy }}
      style={({ pressed }) => [
        compact ? styles.buttonCompact : styles.button,
        { backgroundColor: palette.bg, opacity: disabled ? 0.4 : pressed ? 0.7 : 1 },
      ]}>
      {busy ? (
        <ActivityIndicator color={palette.fg} />
      ) : (
        <>
          {icon && <SymbolView name={icon} size={16} tintColor={palette.fg} />}
          <ThemedText type={compact ? 'smallBold' : 'default'} style={{ color: palette.fg }}>
            {title}
          </ThemedText>
        </>
      )}
    </Pressable>
  );
}

export function Field({
  label,
  error,
  hint,
  style,
  ...input
}: TextInputProps & { label: string; error?: string; hint?: string }) {
  const theme = useTheme();
  return (
    <View style={styles.field}>
      <ThemedText type="smallBold">{label}</ThemedText>
      <TextInput
        placeholderTextColor={theme.textSecondary}
        style={[
          styles.input,
          {
            backgroundColor: theme.backgroundElement,
            color: theme.text,
            borderColor: error ? theme.danger : 'transparent',
          },
          input.multiline && styles.multiline,
          style,
        ]}
        accessibilityLabel={label}
        {...input}
      />
      {error ? (
        <ThemedText type="small" style={{ color: theme.danger }}>
          {error}
        </ThemedText>
      ) : hint ? (
        <ThemedText type="small" themeColor="textSecondary">
          {hint}
        </ThemedText>
      ) : null}
    </View>
  );
}

/** Pick one of a few options, e.g. a segment or a workout color. */
export function Choice<T extends string | number | null>({
  options,
  value,
  onChange,
  render,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  render?: (option: { value: T; label: string }, selected: boolean) => ReactNode;
}) {
  const theme = useTheme();
  return (
    <View style={styles.choices} accessibilityRole="radiogroup">
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <Pressable
            key={String(option.value)}
            onPress={() => onChange(option.value)}
            accessibilityRole="radio"
            accessibilityState={{ selected }}
            accessibilityLabel={option.label}
            style={[
              styles.choice,
              {
                backgroundColor: selected ? theme.accent : theme.backgroundElement,
              },
            ]}>
            {render ? (
              render(option, selected)
            ) : (
              <ThemedText type="small" style={{ color: selected ? theme.onAccent : theme.text }}>
                {option.label}
              </ThemedText>
            )}
          </Pressable>
        );
      })}
    </View>
  );
}

export function Banner({ tone = 'info', children }: PropsWithChildren<{ tone?: 'info' | 'warning' | 'error' }>) {
  const theme = useTheme();
  const colors = {
    info: { bg: theme.backgroundElement, fg: theme.textSecondary },
    warning: { bg: theme.warningBackground, fg: theme.warning },
    error: { bg: theme.backgroundElement, fg: theme.danger },
  }[tone];
  return (
    <View style={[styles.banner, { backgroundColor: colors.bg }]} accessibilityRole="alert">
      <ThemedText type="small" style={{ color: colors.fg }}>
        {children}
      </ThemedText>
    </View>
  );
}

export function EmptyState({ title, message, action }: { title: string; message?: string; action?: ReactNode }) {
  return (
    <View style={styles.empty}>
      <ThemedText type="smallBold" style={styles.center}>
        {title}
      </ThemedText>
      {message ? (
        <ThemedText type="small" themeColor="textSecondary" style={styles.center}>
          {message}
        </ThemedText>
      ) : null}
      {action}
    </View>
  );
}

export function Loading() {
  return (
    <View style={styles.empty}>
      <ActivityIndicator />
    </View>
  );
}

/** The offline / error line most data screens show above their content. */
export function ResourceStatus({
  offline,
  error,
  fetchedAt,
  hasData,
}: {
  offline: boolean;
  error: string | null;
  fetchedAt: string | null;
  hasData: boolean;
}) {
  if (offline) {
    const when = fetchedAt
      ? new Date(fetchedAt).toLocaleString(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' })
      : null;
    return (
      <Banner tone="warning">
        {hasData && when ? `Offline. Showing what was saved ${when}.` : 'Offline. Connect to load this.'}
      </Banner>
    );
  }
  if (error) return <Banner tone="error">{error}</Banner>;
  return null;
}

const styles = StyleSheet.create({
  screen: {
    width: '100%',
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
    padding: Spacing.three,
    paddingBottom: Spacing.six,
    gap: Spacing.four,
  },
  pageTitle: { gap: 2, paddingTop: Spacing.two },
  section: { gap: Spacing.two },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.one,
  },
  sectionTitle: { textTransform: 'uppercase', letterSpacing: 0.6, fontSize: 12 },
  card: { borderRadius: Spacing.three, padding: Spacing.three, gap: Spacing.two },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.three,
    paddingHorizontal: Spacing.three,
    paddingVertical: 12,
    borderRadius: Spacing.three,
    minHeight: 52,
  },
  rowText: { flex: 1, gap: 2 },
  button: {
    flexDirection: 'row',
    gap: Spacing.two,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 50,
    paddingHorizontal: Spacing.four,
    borderRadius: Spacing.three,
  },
  buttonCompact: {
    flexDirection: 'row',
    gap: Spacing.one,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 36,
    paddingHorizontal: Spacing.three,
    borderRadius: 18,
  },
  field: { gap: Spacing.one },
  input: {
    fontSize: 16,
    paddingHorizontal: Spacing.three,
    paddingVertical: 12,
    borderRadius: 12,
    borderWidth: 1,
  },
  multiline: { minHeight: 96, textAlignVertical: 'top' },
  choices: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.two },
  choice: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 18, minHeight: 36, justifyContent: 'center' },
  banner: { borderRadius: 12, paddingHorizontal: Spacing.three, paddingVertical: 10 },
  empty: { alignItems: 'center', gap: Spacing.two, paddingVertical: Spacing.five },
  center: { textAlign: 'center' },
});
