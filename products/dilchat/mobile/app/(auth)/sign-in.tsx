import React, { useState } from "react";
import { Link } from "expo-router";

import { useAuth } from "@/auth/AuthContext";
import { userMessageFor } from "@/api/errors";
import { Body, Button, ErrorText, Heading, Screen, TextField } from "@/ui/components";

export default function SignIn(): React.ReactElement {
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (): Promise<void> => {
    setError(null);
    if (!email.trim() || !password) {
      setError("Enter your email and password.");
      return;
    }
    setBusy(true);
    try {
      await signIn(email.trim(), password);
    } catch (e) {
      setError(userMessageFor(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen>
      <Heading>Sign in</Heading>
      <Body muted>Access your DilChat account.</Body>
      <TextField
        label="Email"
        testID="email"
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        keyboardType="email-address"
        textContentType="emailAddress"
        autoComplete="email"
      />
      <TextField
        label="Password"
        testID="password"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        textContentType="password"
        autoComplete="current-password"
      />
      <ErrorText>{error}</ErrorText>
      <Button title="Sign in" testID="submit" onPress={onSubmit} loading={busy} />
      <Link href="/(auth)/register" accessibilityRole="link">
        <Body>Need an account? Create one.</Body>
      </Link>
    </Screen>
  );
}
