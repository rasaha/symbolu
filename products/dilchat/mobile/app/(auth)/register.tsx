import React, { useState } from "react";
import { useRouter } from "expo-router";

import { useAuth } from "@/auth/AuthContext";
import { userMessageFor } from "@/api/errors";
import { Body, Button, ErrorText, Heading, Screen, TextField } from "@/ui/components";

export default function Register(): React.ReactElement {
  const { register, signIn } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (): Promise<void> => {
    setError(null);
    if (!email.trim() || !password) {
      setError("Enter an email and password.");
      return;
    }
    if (password.length < 8) {
      setError("Use a password of at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      await register(email.trim(), password);
      await signIn(email.trim(), password);
    } catch (e) {
      setError(userMessageFor(e));
      setBusy(false);
    }
  };

  return (
    <Screen>
      <Heading>Create account</Heading>
      <Body muted>Each person keeps their own private account and birth profile.</Body>
      <TextField label="Email" testID="email" value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" autoComplete="email" />
      <TextField label="Password" testID="password" value={password} onChangeText={setPassword} secureTextEntry autoComplete="password-new" />
      <TextField label="Confirm password" testID="confirm" value={confirm} onChangeText={setConfirm} secureTextEntry autoComplete="password-new" />
      <ErrorText>{error}</ErrorText>
      <Button title="Create account" testID="submit" onPress={onSubmit} loading={busy} />
      <Button title="Back to sign in" variant="secondary" onPress={() => router.back()} />
    </Screen>
  );
}
