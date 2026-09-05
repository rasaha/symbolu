/**
 * Small, accessible, production-restrained UI primitives shared by all screens.
 * Large touch targets, screen-reader labels, dynamic-type-friendly sizing,
 * visible loading/disabled states. No branding or animation this phase.
 */
import React from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type TextInputProps,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

export const colors = {
  bg: "#faf9fb",
  surface: "#ffffff",
  text: "#1c1b22",
  muted: "#5c5b66",
  border: "#d8d6de",
  primary: "#3a2f6b",
  primaryText: "#ffffff",
  danger: "#8a1c2b",
  disabled: "#b9b7c2",
};

export function Screen({ children, scroll = true }: { children: React.ReactNode; scroll?: boolean }): React.ReactElement {
  const inner = <View style={styles.screenInner}>{children}</View>;
  return (
    <SafeAreaView style={styles.screen} edges={["top", "bottom"]}>
      {scroll ? (
        <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.scrollContent}>
          {inner}
        </ScrollView>
      ) : (
        inner
      )}
    </SafeAreaView>
  );
}

export function Heading({ children }: { children: React.ReactNode }): React.ReactElement {
  return (
    <Text accessibilityRole="header" style={styles.heading}>
      {children}
    </Text>
  );
}

export function Body({ children, muted }: { children: React.ReactNode; muted?: boolean }): React.ReactElement {
  return <Text style={[styles.body, muted && styles.muted]}>{children}</Text>;
}

export function ErrorText({ children }: { children: React.ReactNode }): React.ReactElement | null {
  if (!children) return null;
  return (
    // Errors are announced assertively (interrupting) so a screen-reader user is
    // told immediately; `alert` role gives iOS VoiceOver the same behavior. The
    // red color is never the only signal — the text itself states the problem.
    <Text accessibilityRole="alert" accessibilityLiveRegion="assertive" style={styles.error}>
      {children}
    </Text>
  );
}

export function Button({
  title,
  onPress,
  loading,
  disabled,
  variant = "primary",
  testID,
}: {
  title: string;
  onPress: () => void;
  loading?: boolean;
  disabled?: boolean;
  variant?: "primary" | "secondary" | "danger";
  testID?: string;
}): React.ReactElement {
  const isDisabled = disabled || loading;
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityState={{ disabled: !!isDisabled, busy: !!loading }}
      accessibilityLabel={title}
      disabled={isDisabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        variant === "secondary" && styles.buttonSecondary,
        variant === "danger" && styles.buttonDanger,
        isDisabled && styles.buttonDisabled,
        pressed && !isDisabled && styles.buttonPressed,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={variant === "secondary" ? colors.primary : colors.primaryText} />
      ) : (
        <Text style={[styles.buttonText, variant === "secondary" && styles.buttonTextSecondary]}>{title}</Text>
      )}
    </Pressable>
  );
}

export function TextField({
  label,
  error,
  testID,
  ...rest
}: { label: string; error?: string; testID?: string } & TextInputProps): React.ReactElement {
  return (
    <View style={styles.fieldWrap}>
      <Text style={styles.label} nativeID={`${testID ?? label}-label`}>
        {label}
      </Text>
      <TextInput
        testID={testID}
        accessibilityLabel={label}
        accessibilityLabelledBy={`${testID ?? label}-label`}
        placeholderTextColor={colors.muted}
        style={[styles.input, error ? styles.inputError : null]}
        {...rest}
      />
      <ErrorText>{error}</ErrorText>
    </View>
  );
}

export function Card({ children }: { children: React.ReactNode }): React.ReactElement {
  return <View style={styles.card}>{children}</View>;
}

export function Loading({ label }: { label?: string }): React.ReactElement {
  return (
    <View
      accessible
      accessibilityRole="progressbar"
      accessibilityLabel={label ?? "Loading"}
      accessibilityLiveRegion="polite"
      style={styles.loading}
    >
      <ActivityIndicator color={colors.primary} />
      {label ? <Body muted>{label}</Body> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  screenInner: { padding: 20, gap: 16 },
  scrollContent: { flexGrow: 1 },
  heading: { fontSize: 24, fontWeight: "700", color: colors.text },
  body: { fontSize: 16, lineHeight: 22, color: colors.text },
  muted: { color: colors.muted },
  error: { fontSize: 14, color: colors.danger, marginTop: 4 },
  button: {
    minHeight: 52,
    borderRadius: 12,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 20,
  },
  buttonSecondary: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border },
  buttonDanger: { backgroundColor: colors.danger },
  buttonDisabled: { backgroundColor: colors.disabled },
  buttonPressed: { opacity: 0.85 },
  buttonText: { color: colors.primaryText, fontSize: 16, fontWeight: "600" },
  buttonTextSecondary: { color: colors.primary },
  fieldWrap: { gap: 6 },
  label: { fontSize: 14, fontWeight: "600", color: colors.text },
  input: {
    minHeight: 48,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    paddingHorizontal: 14,
    fontSize: 16,
    color: colors.text,
    backgroundColor: colors.surface,
  },
  inputError: { borderColor: colors.danger },
  card: { backgroundColor: colors.surface, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 16, gap: 10 },
  loading: { flex: 1, alignItems: "center", justifyContent: "center", gap: 12, padding: 24 },
});
