package com.example.androidapp;

import android.content.Intent;
import android.os.Bundle;
import android.provider.MediaStore;
import android.view.View;
import android.widget.Button;
import android.widget.Toast;

import androidx.activity.ComponentActivity;

public class HomeActivity extends ComponentActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_home);

        Button btnCamera = findViewById(R.id.btnCamera);
        Button btnGallery = findViewById(R.id.btnGallery);
        Button btnUpload = findViewById(R.id.btnUpload);
        Button btnDownload = findViewById(R.id.btnDownload);

        btnCamera.setOnClickListener(v -> {
            Intent intent = new Intent(HomeActivity.this, MainActivity.class);
            startActivity(intent);
        });


        btnGallery.setOnClickListener(v -> {
            Intent intent = new Intent(Intent.ACTION_PICK, MediaStore.Images.Media.EXTERNAL_CONTENT_URI);
            intent.setType("image/*");

            try {
                startActivity(intent);
            } catch (Exception e) {
                Toast.makeText(HomeActivity.this, "No gallery app found", Toast.LENGTH_SHORT).show();
            }
        });

        btnUpload.setOnClickListener(v ->
                Toast.makeText(HomeActivity.this,
                        "Upload to server coming soon",
                        Toast.LENGTH_SHORT).show()
        );

        btnDownload.setOnClickListener(v ->
                Toast.makeText(HomeActivity.this,
                        "Download from server coming soon",
                        Toast.LENGTH_SHORT).show()
        );
    }
}
