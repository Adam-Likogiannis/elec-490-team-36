package com.example.androidapp;

import android.net.Uri;
import android.os.Bundle;
import android.widget.ImageView;
import android.widget.Toast;

import androidx.activity.ComponentActivity;

public class ViewImageActivity extends ComponentActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_view_image);

        ImageView img = findViewById(R.id.imgView);

        Uri uri = getIntent().getData();
        if (uri == null) {
            Toast.makeText(this, "No image selected", Toast.LENGTH_SHORT).show();
            finish();
            return;
        }

        img.setImageURI(uri);
    }
}