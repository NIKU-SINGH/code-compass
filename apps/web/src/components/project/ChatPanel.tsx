"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Square, ChevronDown, Bot, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

const PLACEHOLDER_MESSAGES: Message[] = [
  {
    id: "1",
    role: "assistant",
    content: "Hi! I've indexed this repository. Ask me anything about the codebase — architecture, specific functions, data flow, or dependencies.",
    timestamp: new Date(),
  },
];

const MODELS = ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5"];

export function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>(PLACEHOLDER_MESSAGES);
  const [input, setInput] = useState("");
  const [model, setModel] = useState(MODELS[0]);
  const [isStreaming, setIsStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function handleSend() {
    const trimmed = input.trim();
    if (!trimmed) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: trimmed,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsStreaming(true);

    // Placeholder response — will wire up to /api/chat
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: "This is a placeholder response. The chat API is not yet connected.",
          timestamp: new Date(),
        },
      ]);
      setIsStreaming(false);
    }, 600);
  }

  function handleStop() {
    setIsStreaming(false);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="w-[380px] shrink-0 flex flex-col border-r border-border overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border shrink-0">
        <h2 className="text-sm font-semibold text-foreground">Chat</h2>
        <p className="text-xs text-muted-foreground mt-0.5">Ask questions about the codebase</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-4">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
            <div
              className={`size-7 rounded-full flex items-center justify-center shrink-0 ${
                msg.role === "assistant"
                  ? "bg-primary/10 text-primary"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              {msg.role === "assistant" ? (
                <Bot className="size-4" />
              ) : (
                <User className="size-4" />
              )}
            </div>
            <div
              className={`max-w-[80%] rounded-xl px-3.5 py-2.5 text-sm leading-relaxed ${
                msg.role === "assistant"
                  ? "bg-muted text-foreground"
                  : "bg-primary text-primary-foreground"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="p-3 shrink-0">
        <div className="rounded-xl border border-border bg-muted/30 focus-within:border-border/80 transition-colors">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything about the codebase..."
            rows={2}
            className="resize-none border-0 bg-transparent shadow-none focus-visible:ring-0 text-sm leading-relaxed px-3 pt-3 pb-1 min-h-0"
          />
          <div className="flex items-center justify-between px-2 pb-2 pt-1">
            {/* Model selector */}
            <div className="relative">
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="appearance-none bg-transparent text-xs text-muted-foreground pr-5 pl-1 py-1 rounded cursor-pointer hover:text-foreground focus:outline-none focus:text-foreground transition-colors"
              >
                {MODELS.map((m) => (
                  <option key={m} value={m} className="bg-popover text-foreground">
                    {m}
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-0 top-1/2 -translate-y-1/2 size-3 text-muted-foreground" />
            </div>
            {/* Send / Stop */}
            {isStreaming ? (
              <Button
                size="icon"
                onClick={handleStop}
                className="size-7 rounded-full bg-destructive hover:bg-destructive/90 text-destructive-foreground shrink-0"
              >
                <Square className="size-3 fill-current" />
              </Button>
            ) : (
              <Button
                size="icon"
                onClick={handleSend}
                disabled={!input.trim()}
                className="size-7 rounded-full shrink-0"
              >
                <Send className="size-3" />
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
