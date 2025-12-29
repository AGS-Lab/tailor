"use client";

import * as React from "react";
import { Send, User, Bot, Menu, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

interface Message {
    role: "user" | "assistant" | "tool";
    content: string;
    name?: string; // For tool outputs
}

export function ChatInterface() {
    const [input, setInput] = React.useState("");
    const [messages, setMessages] = React.useState<Message[]>([
        { role: "assistant", content: "Hello! I'm Tailor. How can I adapt to your work today?" }
    ]);
    const [isLoading, setIsLoading] = React.useState(false);

    const sendMessage = async () => {
        if (!input.trim()) return;

        const userMsg: Message = { role: "user", content: input };
        setMessages((prev) => [...prev, userMsg]);
        setInput("");
        setIsLoading(true);

        try {
            const response = await fetch("http://localhost:8000/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: userMsg.content,
                    // We pass full history in a real app, but for now let's just send the message
                    // and let the backend (which we simple-impl'd) handle it.
                    // Wait, backend expects history list.
                    history: messages.map(m => ({ role: m.role, content: m.content }))
                }),
            });

            if (!response.ok) {
                throw new Error("Failed to fetch");
            }

            const data = await response.json();
            const botMsg: Message = { role: "assistant", content: data.response };
            setMessages((prev) => [...prev, botMsg]);
        } catch (error) {
            console.error(error);
            setMessages((prev) => [...prev, { role: "assistant", content: "Sorry, something went wrong. Is the backend running?" }]);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="flex h-screen w-full bg-neutral-900 text-neutral-100 font-sans overflow-hidden">
            {/* Sidebar (Visual only for now) */}
            <div className="hidden md:flex w-64 flex-col border-r border-neutral-800 bg-neutral-950 p-4">
                <div className="flex items-center gap-2 mb-8">
                    <div className="h-8 w-8 rounded-lg bg-indigo-500 flex items-center justify-center">
                        <span className="text-white font-bold">T</span>
                    </div>
                    <h1 className="text-xl font-bold tracking-tight">Tailor</h1>
                </div>

                <div className="space-y-2">
                    <h2 className="text-xs font-semibold text-neutral-500 uppercase tracking-wider">Active Plugins</h2>
                    <div className="p-2 rounded bg-neutral-900/50 text-sm text-neutral-400 border border-neutral-800">
                        Memory
                    </div>
                    <div className="p-2 rounded bg-neutral-900/50 text-sm text-neutral-400 border border-neutral-800">
                        File Context
                    </div>
                </div>

                <div className="mt-auto">
                    <button className="flex items-center gap-2 text-sm text-neutral-500 hover:text-white transition-colors">
                        <Settings className="w-4 h-4" />
                        Configure
                    </button>
                </div>
            </div>

            {/* Main Chat Area */}
            <div className="flex-1 flex flex-col h-full relative">
                {/* Header */}
                <div className="h-14 border-b border-neutral-800 flex items-center px-6 justify-between bg-neutral-900/50 backdrop-blur-sm z-10">
                    <span className="text-sm text-neutral-400">Standard Mode</span>
                    {/* Mobile menu toggle would go here */}
                </div>

                {/* Messages */}
                <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6 scroll-smooth">
                    {messages.map((msg, i) => (
                        <div
                            key={i}
                            className={cn(
                                "flex w-full max-w-3xl mx-auto gap-4",
                                msg.role === "user" ? "justify-end" : "justify-start"
                            )}
                        >
                            {msg.role !== "user" && (
                                <div className="w-8 h-8 rounded-full bg-indigo-600/20 flex-shrink-0 flex items-center justify-center border border-indigo-500/30">
                                    <Bot className="w-4 h-4 text-indigo-400" />
                                </div>
                            )}

                            <div
                                className={cn(
                                    "relative max-w-[80%] px-5 py-3 rounded-2xl text-sm leading-relaxed shadow-sm",
                                    msg.role === "user"
                                        ? "bg-indigo-600 text-white rounded-tr-sm"
                                        : "bg-neutral-800 text-neutral-200 rounded-tl-sm border border-neutral-700/50"
                                )}
                            >
                                {msg.content}
                            </div>

                            {msg.role === "user" && (
                                <div className="w-8 h-8 rounded-full bg-neutral-700 flex-shrink-0 flex items-center justify-center">
                                    <User className="w-4 h-4 text-neutral-400" />
                                </div>
                            )}
                        </div>
                    ))}
                    {isLoading && (
                        <div className="flex w-full max-w-3xl mx-auto gap-4 justify-start">
                            <div className="w-8 h-8 rounded-full bg-indigo-600/20 flex-shrink-0 flex items-center justify-center border border-indigo-500/30">
                                <Bot className="w-4 h-4 text-indigo-400" />
                            </div>
                            <div className="bg-neutral-800/50 px-5 py-3 rounded-2xl rounded-tl-sm items-center flex">
                                <div className="w-2 h-2 bg-neutral-500 rounded-full animate-bounce mr-1"></div>
                                <div className="w-2 h-2 bg-neutral-500 rounded-full animate-bounce mr-1 delay-75"></div>
                                <div className="w-2 h-2 bg-neutral-500 rounded-full animate-bounce delay-150"></div>
                            </div>
                        </div>
                    )}
                </div>

                {/* Input Area */}
                <div className="p-4 md:p-6 bg-neutral-900 border-t border-neutral-800">
                    <div className="max-w-3xl mx-auto relative flex items-center gap-2">
                        <input
                            type="text"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
                            placeholder="Ask Tailor..."
                            className="flex-1 bg-neutral-800 border-none rounded-xl px-4 py-3 text-neutral-200 placeholder-neutral-500 focus:ring-2 focus:ring-indigo-500/50 focus:outline-none transition-all shadow-inner"
                        />
                        <button
                            onClick={sendMessage}
                            disabled={isLoading || !input.trim()}
                            className="p-3 rounded-xl bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-indigo-900/20 active:scale-95"
                        >
                            <Send className="w-4 h-4" />
                        </button>
                    </div>
                    <p className="text-center text-xs text-neutral-600 mt-3">
                        Tailor can make mistakes. Verify important information.
                    </p>
                </div>
            </div>
        </div>
    );
}
