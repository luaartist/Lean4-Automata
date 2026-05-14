package main

import (
	"log"
	"net/http"
)

func main() {
	if err := initForumDB(); err != nil {
		log.Fatalf("failed to initialize forum database: %v", err)
	}

	registerForumRoutes()

	addr := getEnv("LEAN4A_FORUM_ADDR", ":8443")
	log.Printf("Lean4-Automata forum harness listening on %s", addr)
	if err := http.ListenAndServe(addr, nil); err != nil {
		log.Fatalf("forum harness stopped: %v", err)
	}
}
